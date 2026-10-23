#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
答案可吸收性（absorption）——口径 B：Citability 五子项 20 分制 × 0.75 = 15 分。

与 geo_ready 的 `WebsiteAnalyzer::Analyzers::CitabilityAnalyzer` 逐步对齐，
两侧对同一站点必须得出同一个可吸收性分数（此前 skill 用「可引用率曲线 + FAQ 3」
的简化口径，与产品实现是两套模型，同一站点两边分数不一致）。

子项与满分（原始 20 分制，最后 × 0.75 折算到维度 15 分）：

| # | 子项 | 原始分 | 判定 |
|---|---|---|---|
| 1 | 内容块可引用率 | 7 | 可引用块占比，锚点 0→0 / 10→3 / 25→5 / 40→7（线性插值） |
| 2 | 证据块覆盖 | 7 | 定义/数据/对比/步骤四类，每类 ≥2 块且密度 ≥2% 记有效；4→7 / 3→5 / 2→3 / 1→1 |
| 3 | 直接回答 | 3 | 每页首个正文段 40–150 词且含数据或定义；覆盖率 ≥60→3 / ≥30→2 / >0→1 |
| 4 | 结构化答案资产 | 2 | 摘要小节 + 数据表格 + 答案列表 + FAQ 答案，合计 ≥5→2 / >0→1 |
| 5 | 对题度 | 1 | 标题/H1 与首段主题词重合，或存在提问式小标题；覆盖率 ≥50 计 1 |

只用标准库（html.parser）构建轻量 DOM，不依赖 bs4/lxml，保证 skill 在任何
Python 3 环境可跑。
"""

import re
from html.parser import HTMLParser

# ── 常量：与 Ruby 侧保持一致 ────────────────────────────────────────
IDEAL_WORD_MIN = 100
IDEAL_WORD_MAX = 200
CJK_PARAGRAPH_WORD_MIN = 60
CJK_PARAGRAPH_WORD_MAX = 220
STRUCTURED_WORD_MIN = 30
STRUCTURED_WORD_MAX = 220
MIN_BLOCK_CHARS = 80

DATA_PATTERNS = [re.compile(p, re.I) for p in (
    r"\d+(?:\.\d+)?\s*%",
    r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?",
    r"\$\s?\d+(?:\.\d+)?\s*(?:k|m|b|million|billion)\b",
    r"\b\d{4}年",
    r"\b\d+(?:\.\d+)?\s*(?:x|times|倍)\b",
    r"\b\d+(?:\.\d+)?\s*(?:kg|km|cm|mm|gb|mb|tb|ms|seconds?|minutes?|hours?|days?)\b",
    r"\b\d+\s?(?:个|人|次|页|项|天|小时|分钟|秒|元|美元|公里|米)",
    r"\b\d{1,3}(?:,\d{3})+\b",
)]

# 与 Ruby 侧一致：不加词边界（`many|some|various|several|etc` 直接在子串上匹配），
# 加 \b 会漏掉 somewhat / somewhere 这类写法，导致同一段落在两侧判定不同。
VAGUE_PATTERNS = [re.compile(p, re.I) for p in (
    r"many", r"some", r"various", r"several", r"etc\.?",
    r"很多", r"一些", r"各种", r"等等",
)]

DEFINITION_PATTERNS = [re.compile(p, re.I) for p in (
    r"\bmeans\b", r"\brefers? to\b", r"\bis defined as\b", r"\bis known as\b",
    r"\bstands for\b", r"\bdefined as\b",
    r"定义", r"是指", r"指的是", r"主要是指", r"通常指", r"所谓", r"是一种",
    r"是一类", r"是一项", r"是一个", r"是一套", r"为一种", r"为一类",
    r"表示一种", r"意思是", r"含义是",
)]

COMPARISON_PATTERNS = [re.compile(p, re.I) for p in (
    r"\bvs\.?\b", r"\bversus\b", r"\bcompare\b", r"\bcompared with\b",
    r"\bcompared to\b", r"\bbetter than\b", r"\bdifference between\b",
    r"区别", r"对比", r"相比", r"优缺点", r"不同", r"差异",
)]

STEP_PATTERNS = [re.compile(p, re.I) for p in (
    r"\bstep\s+\d+\b", r"\bsteps?\s*[:：]", r"\b(?:first(?:ly)?|second(?:ly)?|third(?:ly)?|finally)\s*,",
    r"\bhow\s+to\s+\w+", r"步骤\s*\d+", r"步骤[:：]", r"流程[:：]",
    r"首先[，,]", r"其次[，,]", r"最后[，,]", r"第[一二三四五六七八九十]步",
)]

SUMMARY_HEADING_PATTERN = re.compile(
    r"summary|tl;?dr|key\s*takeaways?|highlights?|at\s*a\s*glance|要点|总结|摘要", re.I)

QUESTION_HEADING_PATTERN = re.compile(
    r"what|why|how|when|which|best|compare|什么|为什么|如何|怎么|区别|对比|步骤|适用", re.I)

_ASCII_WS = " \t\r\n\f\v"


def _normalize_text(text):
    r"""对齐 Ruby：`text.to_s.strip.gsub(/\s+/, ' ')` 里的 \s 只匹配 ASCII 空白。

    Python 的 str.strip() 会连 &nbsp;（\xa0）一起吃掉，Ruby 不会——不显式用
    ASCII 字符集，同一段落在两侧的结尾字符不同，自包含判定与词数都会漂移。
    """
    return re.sub(r"[ \t\r\n\f\v]+", " ", text or "").strip(_ASCII_WS)


_STOP_TERMS = {"the", "and", "for", "with", "from", "this", "that", "your",
               "you", "are", "has", "have", "what", "why", "how", "when",
               "which"}


# ── 轻量 DOM ───────────────────────────────────────────────────────
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
              "link", "meta", "param", "source", "track", "wbr"}
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "iframe", "object"}
_AUTO_CLOSE_ON_START = {
    "p": {"p"},
    "li": {"li"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
    "tr": {"tr"},
    "td": {"td", "th", "tr"},
    "th": {"td", "th", "tr"},
    "option": {"option"},
}
_BLOCKISH = {"p", "div", "section", "article", "ul", "ol", "table", "dl",
             "details", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
             "pre", "figure", "form", "main", "aside", "header", "footer"}

_NON_CONTENT_TAGS = {"nav", "header", "footer", "script", "style", "noscript"}
_NON_CONTENT_ROLES = {"navigation", "banner", "contentinfo", "dialog"}
_NON_CONTENT_ID_RE = re.compile(
    r"\A(site-|global-)?(nav|navbar|menu|header|footer|sidebar|cookie|modal)\Z", re.I)
_NON_CONTENT_CLASS_RE = re.compile(
    r"\A(site-|global-|main-)?(nav|navbar|menu|header|footer|sidebar|cookie|modal)(-[a-z0-9]+)?\Z",
    re.I)
_FAQ_TOKENS = ("faq", "accordion", "question")
_FAQ_PREFIX_RE = re.compile(r"(?:faq|accordion|question)-", re.I)
_FAQ_ID_RE = re.compile(r"\Afaq(?:[-_].*)?\Z", re.I)


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent", "text_cache")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.parent = parent
        self.text_cache = None


class _DOMParser(HTMLParser):
    """宽松的 HTML → 树。真实页面常省略 </p> </li>，这里做最基本的隐式闭合。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document")
        self.stack = [self.root]
        self.skip = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.skip:
            if tag in _SKIP_TAGS:
                self.skip.append(tag)
            return
        if tag in _SKIP_TAGS:
            self.skip = [tag]
            return

        top = self.stack[-1]
        closers = _AUTO_CLOSE_ON_START.get(tag) or set()
        if top.tag in closers or (top.tag == "p" and tag in _BLOCKISH):
            self.stack.pop()

        node = _Node(tag, {k.lower(): (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self.stack.append(node)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.skip or not data.strip():
            return
        self.stack[-1].children.append(data)


def _collect_text(node, out):
    """收集后代文本（不做 strip，否则会吃掉跨节点边界的空格）。"""
    for child in node.children:
        if isinstance(child, str):
            out.append(child)
        elif child.tag not in _SKIP_TAGS:
            _collect_text(child, out)


def node_text(node):
    """节点全部后代文本（空白归一），带缓存。

    与 Ruby 侧一致：用空串拼接、只把 ASCII 空白折叠成单空格。
    递归时不能对子节点各自 strip —— `Not <span>sure</span>` 会变成 `Notsure`。
    """
    if node.text_cache is not None:
        return node.text_cache
    out = []
    _collect_text(node, out)
    node.text_cache = _normalize_text("".join(out))
    return node.text_cache


def iter_nodes(node, tags=None):
    for child in node.children:
        if isinstance(child, str) or child.tag in _SKIP_TAGS:
            continue
        if tags is None or child.tag in tags:
            yield child
        for sub in iter_nodes(child, tags):
            yield sub


def _non_content_container(node):
    if node.tag in _NON_CONTENT_TAGS:
        return True
    if (node.attrs.get("role") or "").lower() in _NON_CONTENT_ROLES:
        return True
    if _NON_CONTENT_ID_RE.match((node.attrs.get("id") or "").strip()):
        return True
    for cls in (node.attrs.get("class") or "").split():
        if _NON_CONTENT_CLASS_RE.match(cls.lower()):
            return True
    return False


def _is_non_content(node):
    cur = node.parent
    while cur is not None:
        if _non_content_container(cur):
            return True
        cur = cur.parent
    return False


def parse_html(html):
    parser = _DOMParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:  # noqa: BLE001 — 畸形 HTML 不应让整份评分失败
        pass
    return parser.root


# ── 文本度量 ───────────────────────────────────────────────────────
def is_cjk(text):
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def word_count(text):
    """等效词数：中文按 1.5 字 ≈ 1 词折算，与 Ruby 侧一致。"""
    text = text or ""
    if is_cjk(text):
        cn = len(re.findall(r"[\u4e00-\u9fff]", text))
        other = len(re.sub(r"[\u4e00-\u9fff]", " ", text).split())
        return int(round(cn / 1.5)) + other
    return len(text.split())


def word_range(type_, text):
    if type_ in ("list_group", "howto_step", "table_summary", "faq_answer", "definition_block"):
        return STRUCTURED_WORD_MIN, STRUCTURED_WORD_MAX
    if is_cjk(text):
        return CJK_PARAGRAPH_WORD_MIN, CJK_PARAGRAPH_WORD_MAX
    return IDEAL_WORD_MIN, IDEAL_WORD_MAX


def is_structured(type_):
    return type_ in ("list_group", "howto_step", "table_summary", "faq_answer", "definition_block")


def self_contained(text):
    if is_cjk(text):
        return len(text) >= 50 and bool(re.search(r"[。？！.?!]$", text))
    return bool(re.match(r"[A-Z]", text)) and bool(re.search(r"[.!?]$", text)) and len(text.split()) >= 5


def has_data(text):
    return any(p.search(text) for p in DATA_PATTERNS)


def count_data_points(text):
    return sum(len(p.findall(text)) for p in DATA_PATTERNS)


def evidence_types(text, type_):
    types = []
    if type_ == "definition_block" or any(p.search(text) for p in DEFINITION_PATTERNS):
        types.append("definition")
    if has_data(text):
        types.append("data")
    first_row = (text or "").split(";")[0]
    if (type_ == "table_summary" and any(p.search(first_row) for p in COMPARISON_PATTERNS)) \
            or any(p.search(text) for p in COMPARISON_PATTERNS):
        types.append("comparison")
    if type_ == "howto_step" or sum(len(p.findall(text)) for p in STEP_PATTERNS) >= 2:
        types.append("step")
    return types


# ── 块抽取 ─────────────────────────────────────────────────────────
def _add_block(blocks, page_url, text, type_):
    text = _normalize_text(text)
    if len(text) >= MIN_BLOCK_CHARS:
        blocks.append({"text": text, "url": page_url, "type": type_})


def _definition_list(node, text):
    if any(p.search(text) for p in DEFINITION_PATTERNS):
        return True
    for child in node.children:
        if isinstance(child, str) or child.tag != "dt":
            continue
        term = node_text(child)
        if 2 <= len(term) <= 60 and not re.search(r"\d", term):
            return True
    return False


def _is_faq_container(node):
    """对齐 Ruby 的 FAQ 选择器：只认 section/div/article 上的 faq/accordion/question 标记。

    早期实现用「任意标签 + 宽松正则」，会把 li/span/a 这类内层节点也算成 FAQ 块，
    块数与可引用块数整体偏高（同一页面实测 90 vs 81）。
    """
    if node.tag not in ("section", "div", "article"):
        return False
    classes = (node.attrs.get("class") or "").split()
    if any(token.lower() in _FAQ_TOKENS for token in classes):
        return True
    if _FAQ_PREFIX_RE.search(node.attrs.get("class") or ""):
        return True
    return bool(_FAQ_ID_RE.match((node.attrs.get("id") or "").strip()))


def extract_blocks(dom, page_url):
    blocks = []

    for node in iter_nodes(dom, {"p", "blockquote"}):
        if _is_non_content(node):
            continue
        _add_block(blocks, page_url, node_text(node), "paragraph")

    for node in iter_nodes(dom, {"ul", "ol"}):
        if _is_non_content(node):
            continue
        items = [node_text(li) for li in node.children
                 if not isinstance(li, str) and li.tag == "li"]
        items = [i for i in items if i]
        if len(items) < 2:
            continue
        _add_block(blocks, page_url, "; ".join(items),
                   "howto_step" if node.tag == "ol" else "list_group")

    for node in iter_nodes(dom, {"table"}):
        if _is_non_content(node):
            continue
        rows = []
        for tr in iter_nodes(node, {"tr"}):
            cells = [node_text(c) for c in tr.children
                     if not isinstance(c, str) and c.tag in ("th", "td")]
            cells = [c for c in cells if c]
            if cells:
                rows.append(" | ".join(cells))
        if len(rows) < 2:
            continue
        _add_block(blocks, page_url, "; ".join(rows[:6]), "table_summary")

    for node in iter_nodes(dom, {"dl"}):
        if _is_non_content(node):
            continue
        parts = [node_text(c) for c in node.children
                 if not isinstance(c, str) and c.tag in ("dt", "dd")]
        parts = [p for p in parts if p]
        if len(parts) < 2:
            continue
        text = "; ".join(parts)
        _add_block(blocks, page_url, text,
                   "definition_block" if _definition_list(node, text) else "list_group")

    for node in iter_nodes(dom, {"details"}):
        if _is_non_content(node):
            continue
        _add_block(blocks, page_url, node_text(node), "faq_answer")

    for node in iter_nodes(dom):
        if _is_faq_container(node) and not _is_non_content(node):
            _add_block(blocks, page_url, node_text(node), "faq_answer")

    return blocks


def score_block(block):
    text = block["text"]
    wc = word_count(text)
    lo, hi = word_range(block["type"], text)
    in_range = lo <= wc <= hi
    vague = any(p.search(text) for p in VAGUE_PATTERNS)
    data = has_data(text)
    complete = is_structured(block["type"]) or self_contained(text)

    issues = []
    if wc < lo:
        issues.append("too_short")
    if wc > hi:
        issues.append("too_long")
    if not data:
        issues.append("no_data")
    if vague:
        issues.append("vague")
    if not complete:
        issues.append("not_complete")

    return dict(block, word_count=wc, in_range=in_range, has_data=data,
                is_vague=vague, self_contained=complete,
                evidence_types=evidence_types(text, block["type"]),
                data_point_count=count_data_points(text),
                citable=in_range and complete and (not vague or data),
                issues=issues)


# ── 子项汇总 ───────────────────────────────────────────────────────
def _first_content_block(dom):
    for node in iter_nodes(dom, {"p", "blockquote"}):
        if _is_non_content(node):
            continue
        text = node_text(node)
        if 40 <= len(text) <= 1200:
            return text
    for node in iter_nodes(dom, {"div"}):
        if _is_non_content(node):
            continue
        if node.parent is None or node.parent.tag not in ("main", "article"):
            continue
        text = node_text(node)
        if 40 <= len(text) <= 1200:
            return text
    return ""


def direct_answer_summary(dom_pages):
    checked = 0
    with_answer = 0
    for dom in dom_pages:
        text = _first_content_block(dom)
        if not text:
            continue
        checked += 1
        wc = word_count(text)
        if wc < 40 or wc > 150:
            continue
        if has_data(text) or any(p.search(text) for p in DEFINITION_PATTERNS):
            with_answer += 1
    return {
        "pages_checked": checked,
        "pages_with_direct_answer": with_answer,
        "coverage_rate": round(with_answer / checked * 100, 1) if checked else 0,
    }


def evidence_summary(scored_blocks, total_blocks):
    counts = {"definition": 0, "data": 0, "comparison": 0, "step": 0}
    for block in scored_blocks:
        for t in block["evidence_types"]:
            if t in counts:
                counts[t] += 1

    def density(n):
        return round(n / total_blocks * 100, 1) if total_blocks else 0

    covered = sum(1 for k in counts if counts[k] > 0)
    dense = sum(1 for k in counts if counts[k] >= 2 and density(counts[k]) >= 2)
    return {
        "definition_blocks": counts["definition"],
        "data_blocks": counts["data"],
        "comparison_blocks": counts["comparison"],
        "step_blocks": counts["step"],
        "covered_types": covered,
        "dense_covered_types": dense,
        "definition_density": density(counts["definition"]),
        "data_density": density(counts["data"]),
        "comparison_density": density(counts["comparison"]),
        "step_density": density(counts["step"]),
    }


def structured_asset_summary(dom_pages, scored_blocks):
    summary_sections = 0
    data_tables = 0
    for dom in dom_pages:
        for node in iter_nodes(dom, {"h1", "h2", "h3", "h4"}):
            if SUMMARY_HEADING_PATTERN.search(node_text(node)):
                summary_sections += 1
        for node in iter_nodes(dom, {"table"}):
            if _is_non_content(node):
                continue
            if len(list(iter_nodes(node, {"tr"}))) >= 2:
                data_tables += 1
    return {
        "summary_sections": summary_sections,
        "data_tables": data_tables,
        "answer_lists": sum(1 for b in scored_blocks if b["type"] in ("list_group", "howto_step")),
        "faq_answers": sum(1 for b in scored_blocks if b["type"] == "faq_answer"),
    }


def _significant_terms(text):
    normalized = (text or "").lower()
    terms = re.findall(r"[a-z0-9]{3,}", normalized)
    for chunk in re.findall(r"[\u4e00-\u9fff]+", normalized):
        for size in (2, 3):
            terms.extend("".join(chunk[i:i + size]) for i in range(len(chunk) - size + 1))
    return [t for t in terms if t not in _STOP_TERMS][:10]


def query_alignment_summary(page_pairs):
    """page_pairs: [(dom, title, h1), ...]"""
    checked = 0
    aligned = 0
    for dom, title, h1 in page_pairs:
        first = _first_content_block(dom)
        if not (title or h1) or not first:
            continue
        checked += 1
        intent = set(_significant_terms("%s %s" % (title, h1)))
        body = set(_significant_terms(first))
        heading_question = any(
            QUESTION_HEADING_PATTERN.search(node_text(h))
            for h in iter_nodes(dom, {"h2", "h3"}))
        if (intent & body) or heading_question:
            aligned += 1
    return {
        "pages_checked": checked,
        "aligned_pages": aligned,
        "coverage_rate": round(aligned / checked * 100, 1) if checked else 0,
    }


# ── 主入口 ─────────────────────────────────────────────────────────
def analyze(pages):
    """pages: analyze.py 的 page dict 列表（需含 html/url/title/h1）。返回子项明细。"""
    doms = [(p, parse_html(p.get("html"))) for p in pages]

    blocks = []
    for page, dom in doms:
        blocks.extend(extract_blocks(dom, page["url"]))
    seen = set()
    unique = []
    for block in blocks:
        key = (block["type"], block["text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(block)

    scored = [score_block(b) for b in unique]
    total_blocks = len(scored)
    citable = [b for b in scored if b["citable"]]
    block_rate = round(len(citable) / total_blocks * 100, 1) if total_blocks else 0
    passages = [b for b in scored if b["type"] == "paragraph"]
    passage_rate = round(
        sum(1 for b in passages if b["citable"]) / len(passages) * 100, 1) if passages else 0

    dom_only = [d for _, d in doms]
    return {
        "content_blocks": {
            "total": total_blocks,
            "citable": len(citable),
            "citability_rate": block_rate,
            "avg_word_count": round(
                sum(b["word_count"] for b in scored) / total_blocks, 1) if total_blocks else 0,
            "by_type": _by_type(unique),
        },
        "passage_rate": passage_rate,
        "evidence_blocks": evidence_summary(scored, total_blocks),
        "direct_answer": direct_answer_summary(dom_only),
        "structured_answer_assets": structured_asset_summary(dom_only, scored),
        "query_alignment": query_alignment_summary(
            [(dom, page.get("title") or "", (page.get("h1") or [""])[0] if page.get("h1") else "")
             for page, dom in doms]),
        "top_issues": _top_issues(scored),
        "sample_non_citable": [
            {"url": b["url"], "type": b["type"], "word_count": b["word_count"],
             "issues": b["issues"], "text": b["text"][:160]}
            for b in scored if not b["citable"]
        ][:5],
    }


def _by_type(blocks):
    counts = {}
    for block in blocks:
        counts[block["type"]] = counts.get(block["type"], 0) + 1
    return counts


def _top_issues(scored):
    counts = {}
    for block in scored:
        if block["citable"]:
            continue
        for issue in block["issues"]:
            counts[issue] = counts.get(issue, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:4])


def _interpolate(value, points):
    v = float(value or 0)
    if v <= points[0][0]:
        return float(points[0][1])
    if v >= points[-1][0]:
        return float(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= v <= x1:
            return y0 + (y1 - y0) * (v - x0) / float(x1 - x0)
    return float(points[-1][1])


def raw_score(detail):
    """五子项 20 分制原始分（与 Ruby CitabilityAnalyzer 一致）。"""
    score = 0.0

    rate = detail["content_blocks"]["citability_rate"]
    score += _interpolate(rate, [(0, 0), (10, 3), (25, 5), (40, 7)])

    # 有效覆盖 = 该类块数 ≥2 且密度 ≥2%（dense_covered_types 已按此口径统计）
    covered = detail["evidence_blocks"]["dense_covered_types"]
    score += {4: 7, 3: 5, 2: 3, 1: 1}.get(covered, 0)

    direct = detail["direct_answer"]["coverage_rate"]
    score += 3 if direct >= 60 else 2 if direct >= 30 else 1 if direct > 0 else 0

    assets = sum(detail["structured_answer_assets"].values())
    score += 2 if assets >= 5 else 1 if assets > 0 else 0

    if detail["query_alignment"]["coverage_rate"] >= 50:
        score += 1
    return min(score, 20.0)


def absorption_score(detail):
    """20 分制 × 0.75 → 维度 15 分。"""
    return round(raw_score(detail) * 0.75, 1)
