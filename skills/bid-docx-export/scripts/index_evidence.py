#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 证据索引（03b_evidence-index.json 生成器）
==============================================================
扫描 <bid>/evidence/ 下的扫描件（PDF 一等公民；图片按 1 页计），
生成 03b_evidence-index.json（契约 0.1，见 assets/evidence-index.schema.json）。

铁律 1：扫描件不作事实来源——issuer/valid_to/seal_position/original_checked
一律留空/false，由维护人从事实库人工填写；fact_ref 仅做文件名与
01b 证据类条目的关键词匹配，匹配不上留空串，不猜。

用法：
  python index_evidence.py --bid <项目/bid目录>
  rc：0＝生成；2＝前置缺失（evidence/ 不存在或为空目录）
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import pdfutil
except ImportError as e:
    print(f"【执行阻断】pdfutil.py 缺失：{e}")
    sys.exit(2)

ATTACH_RE = re.compile(r"^([A-Z]-\d{1,3})[_\-\s．.]?")
TYPE_RULES = [
    ("资质", ["资质", "许可证", "执照", "认证", "证书类", "施工总承包", "总承包壹级", "总承包一级", "总承包特级", "设计甲级"]),
    ("业绩", ["业绩", "合同", "中标"]),
    ("证书", ["证书", "合格证", "检测报告"]),
    ("财务", ["审计", "财务", "报表", "资信"]),
    ("信用", ["信用", "失信", "行贿", "截图"]),
    ("人员", ["建造师", "职称", "社保证明", "身份证"]),
]
IMG_EXT = {".jpg", ".jpeg", ".png"}


def guess_type(name: str) -> str:
    for label, kws in TYPE_RULES:
        if any(k in name for k in kws):
            return label
    return "证明材料"


def common_span(a: str, b: str, minlen: int = 4) -> bool:
    """a 与 b 是否共享一段 ≥minlen 的连续子串（文件名 ↔ 01b 条目名匹配用）。"""
    for i in range(len(a) - minlen + 1):
        if a[i:i + minlen] in b:
            return True
    return False


def load_scan_cards(bid: str):
    """读 03_bid-plan.json 的证据类任务卡（response_form=scan），供 fact_ref 匹配。

    匹配文本用任务卡 notes（含条目名关键词）＋ source_ref；匹配目标：
    03b.items[].fact_ref = 任务卡 source_ref（如 c-0008，指向 01b 招标要求条目）。
    """
    p = os.path.join(bid, "03_bid-plan.json")
    cards = []
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            for it in data.get("items", []):
                if it.get("response_form") == "scan":
                    cards.append((str(it.get("source_ref", "")),
                                  str(it.get("notes", "")) + str(it.get("id", ""))))
        except (json.JSONDecodeError, OSError):
            pass
    return cards


def index_evidence(bid: str) -> int:
    ev_dir = os.path.join(bid, "evidence")
    if not os.path.isdir(ev_dir):
        print("【执行阻断】bid-docx-export 证据索引未执行")
        print(f"原因：{ev_dir} 不存在（证明材料扫描件目录）")
        print("处置：请先按 references/证明材料装配规则.md 准备 evidence/ 目录（PDF/扫描件）")
        return 2
    files = sorted(fn for fn in os.listdir(ev_dir)
                   if os.path.splitext(fn)[1].lower() in IMG_EXT | {".pdf"})
    if not files:
        print("【执行阻断】evidence/ 目录为空（无可索引扫描件）")
        return 2

    cards = load_scan_cards(bid)
    attach_seen = set()
    items = []
    auto_n = 0
    for fn in files:
        ext = os.path.splitext(fn)[1].lower()
        m = ATTACH_RE.match(fn)
        if m:
            attach = m.group(1)
        else:
            auto_n += 1
            attach = None  # 后面统一补 A-NN
        if ext == ".pdf":
            try:
                npages = pdfutil.count_pages(os.path.join(ev_dir, fn))
            except pdfutil.PdfError as e:
                print(f"⚠️ 页数解析失败，按 1 页计并标注：{fn}（{e}）")
                npages = 1
        else:
            npages = 1
        fact_ref = ""
        for cid, text in cards:
            if common_span(fn, text):
                fact_ref = cid
                break
        note = "" if ext == ".pdf" else "图片按 1 页计（建议转为 PDF）"
        if not fact_ref:
            note = (note + "；" if note else "") + "fact_ref 未匹配 01b 证据类条目，须人工挂接"
        items.append({
            "attach_no": attach,
            "id": "",
            "fact_ref": fact_ref,
            "type": guess_type(fn),
            "file": f"evidence/{fn}",
            "pages": f"1-{npages}" if npages > 1 else "1",
            "page_count": npages,
            "issuer": "",
            "valid_to": "",
            "original_checked": False,
            "note": note,
            "seal_position": "",
        })

    # 补齐附件号与 id（附件号序为装配顺序）
    used = {it["attach_no"] for it in items if it["attach_no"]}
    for i, it in enumerate(items, 1):
        if not it["attach_no"]:
            n = 1
            while f"A-{n:02d}" in used:
                n += 1
            it["attach_no"] = f"A-{n:02d}"
            used.add(it["attach_no"])
            if not it["note"]:
                it["note"] = "文件名无附件号前缀，按序自动编号"
        it["id"] = f"ev-{i:03d}"
    def attach_key(s):
        m = re.match(r"^([A-Z])-(\d+)$", s)
        return (m.group(1), int(m.group(2))) if m else (s, 0)

    items.sort(key=lambda x: (attach_key(x["attach_no"]), x["id"]))
    for i, it in enumerate(items, 1):
        it["id"] = f"ev-{i:03d}"

    by_type = {}
    for it in items:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
    out = {
        "schema_version": "0.1",
        "generated_at": _dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "items": items,
        "order": [it["id"] for it in items],
        "stats": {
            "total": len(items),
            "pages_total": sum(it["page_count"] for it in items),
            "by_type": by_type,
        },
    }
    out_p = os.path.join(bid, "03b_evidence-index.json")
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    unmatched = sum(1 for it in items if not it["fact_ref"])
    print(f"证据索引已生成：{out_p}")
    print(f"共 {len(items)} 件 / {out['stats']['pages_total']} 页；类型分布 {by_type}")
    n_fill = sum(1 for it in items if it["type"] in ("资质", "证书", "人员"))
    if n_fill:
        print(f"⚠️ 铁律 1：{n_fill} 件资质/证书/人员类 issuer/valid_to 留空——"
              "须维护人对照扫描件人工补填 03b 的 valid_to（check_evidence 日期一致性才可核）")
    if unmatched:
        print(f"⚠️ {unmatched} 件未匹配到 01b 证据类条目（fact_ref 空，须人工补）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    if not os.path.isdir(args.bid):
        print(f"【执行阻断】bid 目录不存在：{args.bid}")
        return 2
    return index_evidence(args.bid)


if __name__ == "__main__":
    sys.exit(main())


