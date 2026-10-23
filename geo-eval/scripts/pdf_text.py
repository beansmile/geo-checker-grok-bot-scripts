#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轻量 PDF 工具：读取页数、按页提取文字（Chrome/Skia 生成的 PDF）。
仅用于导出后自检，不追求通用性。"""
import re
import sys
import zlib


def _objects(data):
    objs = {}
    for m in re.finditer(rb"(\d+)\s+0\s+obj\b", data):
        n = int(m.group(1)); s = m.end(); e = data.find(b"endobj", s)
        objs[n] = data[s:e if e != -1 else len(data)]
    return objs


def _stream(body):
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    e = body.find(b"endstream", m.end())
    blob = body[m.end():e]
    if b"/FlateDecode" in body[:m.start()]:
        try:
            return zlib.decompress(blob)
        except Exception:
            return blob
    return blob


def _pages(objs):
    cat = next(v for v in objs.values() if b"/Catalog" in v)
    root = int(re.search(rb"/Pages\s+(\d+)\s+0\s+R", cat).group(1))
    out = []

    def walk(n):
        b = objs.get(n, b"")
        if re.search(rb"/Type\s*/Page[^s]", b):
            out.append(n); return
        km = re.search(rb"/Kids\s*\[(.*?)\]", b, re.S)
        if km:
            for r in re.findall(rb"(\d+)\s+0\s+R", km.group(1)):
                walk(int(r))
    walk(root)
    return out


def page_count(path):
    data = open(path, "rb").read()
    return len(_pages(_objects(data)))


def _hex2text(h):
    try:
        bs = bytes.fromhex(h.decode("ascii"))
    except Exception:
        return ""
    if len(bs) % 2:
        bs = b"\x00" + bs
    return bs.decode("utf-16-be", "ignore")


def _cmap(t):
    mp = {}
    for blk in re.findall(rb"beginbfchar(.*?)endbfchar", t, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            mp[int(a, 16)] = _hex2text(b)
    for blk in re.findall(rb"beginbfrange(.*?)endbfrange", t, re.S):
        for m in re.finditer(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<([0-9A-Fa-f]+)>|\[(.*?)\])", blk, re.S):
            lo, hi = int(m.group(1), 16), int(m.group(2), 16)
            if m.group(4):
                base = _hex2text(m.group(4))
                for i in range(hi - lo + 1):
                    if base:
                        mp[lo + i] = base[:-1] + chr(ord(base[-1]) + i)
            else:
                for i, it in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", m.group(5) or b"")):
                    mp[lo + i] = _hex2text(it)
    return mp


def _fonts(objs, page):
    fm = re.search(rb"/Font\s*<<(.*?)>>", objs[page], re.S)
    out = {}
    if not fm:
        return out
    for name, ref in re.findall(rb"/(\w+)\s+(\d+)\s+0\s+R", fm.group(1)):
        fb = objs.get(int(ref), b"")
        two = b"/Type0" in fb
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", fb)
        t = _stream(objs.get(int(tu.group(1)), b"")) if tu else None
        out[name.decode()] = (_cmap(t) if t else {}, 2 if two else 1)
    return out


def page_texts(path):
    data = open(path, "rb").read()
    objs = _objects(data)
    out = []
    for p in _pages(objs):
        cm = re.search(rb"/Contents\s+(\d+)\s+0\s+R", objs[p])
        cs = _stream(objs.get(int(cm.group(1)), b"")) if cm else None
        if not cs:
            out.append(""); continue
        fm = _fonts(objs, p)
        cmap, width = {}, 1
        parts = []
        for tok in re.finditer(rb"/(\w+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]*)>\s*Tj|\(((?:\\.|[^\\()])*)\)\s*Tj|ET", cs):
            g = tok.group(0)
            if g.endswith(b"Tf"):
                cmap, width = fm.get(tok.group(1).decode(), ({}, 1))
            elif tok.group(2) is not None:
                h = tok.group(2)
                if width == 2:
                    h = h if len(h) % 4 == 0 else b"0" + h
                    ids = [int(h[i:i + 4], 16) for i in range(0, len(h), 4)]
                else:
                    h = h if len(h) % 2 == 0 else b"0" + h
                    ids = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
                parts.append("".join(cmap.get(i, "") for i in ids))
            elif tok.group(3) is not None:
                parts.append("".join(cmap.get(b, chr(b) if 32 <= b < 127 else "") for b in tok.group(3)))
            else:
                parts.append(" ")
        out.append(re.sub(r"\s+", " ", "".join(parts)).strip())
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        for i, t in enumerate(page_texts(sys.argv[2]), 1):
            print(f"--- p{i} ---\n{t[:300]}")
    else:
        print(page_count(sys.argv[1]))
