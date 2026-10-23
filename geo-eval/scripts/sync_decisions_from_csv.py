#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 report/expert_review_decisions.csv 的专家决策同步回 expert_review.json。
支持的列：decision(accept/edit/reject/pending)、edited_conclusion_zh、edited_conclusion_en、notes。"""
import csv, json, os, datetime
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P=os.path.join(ROOT,"expert_review.json"); C=os.path.join(ROOT,"report","expert_review_decisions.csv")
ex=json.load(open(P,encoding="utf-8"))
if not os.path.exists(C):
    print("no csv, skip"); raise SystemExit
rows={r["issue_id"]:r for r in csv.DictReader(open(C,encoding="utf-8-sig"))}
changed=0
for it in ex["items"]:
    r=rows.get(it["issue_id"])
    if not r: continue
    d=(r.get("decision") or "").strip().lower()
    if d in ("accept","edit","reject","pending") and d!=it.get("decision"):
        it["decision"]=d; changed+=1
    zh=(r.get("edited_conclusion_zh") or "").strip(); en=(r.get("edited_conclusion_en") or "").strip()
    if zh or en:
        it["edited_conclusion"]={"zh-CN":zh or (it.get("edited_conclusion") or {}).get("zh-CN"),
                                 "en-US":en or (it.get("edited_conclusion") or {}).get("en-US")}
    nt=(r.get("notes") or "").strip()
    if nt: it["notes"]=nt
ex["synced_from_csv_at"]=datetime.datetime.now().astimezone().isoformat()
json.dump(ex, open(P,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
from collections import Counter
print("synced decisions:",dict(Counter(i["decision"] for i in ex["items"])),"| changed:",changed)
