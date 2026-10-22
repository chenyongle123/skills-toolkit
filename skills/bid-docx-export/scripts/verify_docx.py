#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ bid-docx-export — 交付前回读校验（verify_docx.py，计划书 §8.4/§11.3）。

docx/pdf 逐项回读：章名逐字、占位符残留、元数据残留、页数闭合、
暗标标识（blind）；中英文空格为信息态。全过写 stage=exported。
用法：python verify_docx.py --bid <bid目录> [--identity "公司名,人名"]
rc：0＝通过；1＝残留/不符；2＝前置缺失。
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common
import pdfutil

DOCX = "07_out/投标文件.docx"
PDF = "07_out/投标文件_含附件.pdf"
PAG = "07_out/pagination.json"


def docx_text(xml: str) -> str:
    """抽 w:t 文本（含页眉页脚合并场景由调用方分别取）。"""
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


RESIDUALS = ["【待填", "【待确认", "【待核", "[[F:", "[[S:", "[[EV:", "[[C:"]


def xtext_unescape(s: str) -> str:
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')


def verify(bid: str, identities: list) -> int:
    # 入口闸门（F8：出口校验器不得旁路 gate；rc=2 零产物不写状态）
    grc, gmsgs, _gmeta = _common.gate(bid)
    if grc != 0:
        print("【执行阻断】bid-docx-export 回读校验未执行")
        for m in gmsgs:
            print("  " + m)
        print("处置：先闭环闸门问题（见上）后再跑 verify")
        return 2
    for m in gmsgs:
        print("⚠️", m)
    errors, warns = [], []
    dx = os.path.join(bid, DOCX)
    for need, p in (("docx", dx), ("PDF", os.path.join(bid, PDF)), ("pagination", os.path.join(bid, PAG))):
        if not os.path.exists(p):
            print("【执行阻断】bid-docx-export 回读校验未执行")
            print(f"原因：{p} 缺失（先跑 assemble_pdf + export_docx）")
            return 2
    pag = json.load(open(os.path.join(bid, PAG), encoding="utf-8"))
    meta = json.load(open(os.path.join(bid, "00_metadata.json"), encoding="utf-8"))
    outline = json.load(open(os.path.join(bid, "01c_format-outline.json"), encoding="utf-8"))

    with zipfile.ZipFile(dx) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        core = z.read("docProps/core.xml").decode("utf-8")
        app = z.read("docProps/app.xml").decode("utf-8")
        settings = z.read("word/settings.xml").decode("utf-8")
        names = z.namelist()
        hf = "".join(z.read(n).decode("utf-8", "ignore")
                     for n in names if re.match(r"word/(header|footer)\d*\.xml$", n))

    # 1. 章名逐字（01c 顺序）
    doc_text = xtext_unescape(docx_text(doc))
    pos = 0
    for node in outline.get("chapters", []):
        title = str(node.get("title", ""))
        if not title:
            continue
        i = doc_text.find(title, pos)
        if i < 0:
            errors.append(f"章名未按 01c 顺序逐字出现：{node.get('id')}「{title}」")
        else:
            pos = i + len(title)
    # 2. 占位符残留
    for r in RESIDUALS:
        if r in doc_text:
            n = doc_text.count(r)
            errors.append(f"占位符残留：{r} ×{n}（回 ③ 修正后重导）")
    # 3. 元数据残留
    m = re.search(r"<dc:creator>([^<]*)</dc:creator>", core)
    if m and m.group(1).strip():
        errors.append(f"creator 残留：{m.group(1)[:40]}（重跑 scrub_metadata）")
    m = re.search(r"<cp:lastModifiedBy>([^<]*)</cp:lastModifiedBy>", core)
    if m and m.group(1).strip():
        errors.append(f"lastModifiedBy 残留：{m.group(1)[:40]}")
    for pat, label in ((r"<Company>[^<]+</Company>", "Company"),
                       (r"<Template>[^<]+</Template>", "模板路径"),
                       (r"<w:attachedTemplate[^>]*>", "attachedTemplate")):
        if re.search(pat, app) or (label == "attachedTemplate" and re.search(pat, settings)):
            errors.append(f"元数据残留：{label}")
    if "docProps/custom.xml" in names:
        errors.append("自定义属性残留：docProps/custom.xml")
    if "word/comments.xml" in names:
        errors.append("批注残留：word/comments.xml")
    n_ins = len(re.findall(r"<w:ins\b", doc))
    n_del = len(re.findall(r"<w:del\b", doc))
    if n_ins or n_del:
        errors.append(f"修订记录残留：w:ins×{n_ins}/w:del×{n_del}（须人工接受全部修订后重导，脚本不自动改内容）")
    # 4. 页数闭合（PDF 侧真值）
    try:
        npages = pdfutil.count_pages(os.path.join(bid, PDF))
        total = int(pag.get("total_pages", 0))
        body = int(pag.get("body_pages", 0))
        ev = pag.get("evidence", [])
        ev_pages = sum(int(e.get("pages", 0)) for e in ev)
        if npages != total:
            errors.append(f"PDF 实际页数 {npages} ≠ pagination.total_pages {total}")
        if body + ev_pages != total:
            errors.append(f"页数闭合失败：正文 {body} + 证据 {ev_pages} ≠ 总 {total}")
        starts = [int(e["start_page"]) for e in ev]
        for a, b in zip(starts, starts[1:]):
            prev_pages = int(ev[starts.index(a)]["pages"])
            if a + prev_pages != b:
                errors.append(f"证据页码断号：{a} 起始件页数 {prev_pages} ≠ 下一件起始 {b}")
        chs = [(c.get("id"), int(c.get("start_page", 0))) for c in pag.get("chapters", [])]
        for (id1, p1), (id2, p2) in zip(chs, chs[1:]):
            if p2 < p1:
                errors.append(f"章节起始页倒序：{id1}@{p1} → {id2}@{p2}")
    except pdfutil.PdfError as e:
        errors.append(f"PDF 解析失败：{e}")
    # 5. 暗标标识（docx 三面 + PDF 文本层——外部扫描件常在 PDF 里带公司名）
    if meta.get("bid_mode") == "blind" and identities:
        pdf_hits = _common.pdf_identity_hits(os.path.join(bid, PDF), identities)
        for ident in identities:
            if ident and (ident in doc_text or ident in hf or ident in core
                          or ident in pdf_hits):
                where = []
                if ident in doc_text:
                    where.append("正文")
                if ident in hf:
                    where.append("页眉页脚")
                if ident in core:
                    where.append("属性")
                if ident in pdf_hits:
                    where.append("PDF文本层")
                errors.append(f"暗标标识命中[{'/'.join(where)}]：{ident}（内容修改归 ③；位图型扫描件无文本层，另须人工抽检）")
    # 6. 中英文混排空格（信息态）：计划书 §8.7 规则 2——中英文之间**不加**空格，
    #    扫描对象是误加空格（「中文 English」），不是无空格的合规写法。
    n_space = len(re.findall(r"[\u4e00-\u9fff][ \u00a0]+[A-Za-z]|[A-Za-z][ \u00a0]+[\u4e00-\u9fff]", doc_text))
    if n_space:
        warns.append(f"正文存在中英文之间加空格的写法 {n_space} 处（计划书 §8.7 规则 2 不加空格；信息态，回 ③ 统一）")

    md = ["# 交付前回读校验（verify）", "",
          f"> 生成：bid-docx-export verify_docx；docx/pdf/pagination 三源核对；时间：{_dt.datetime.now().astimezone().replace(microsecond=0).isoformat()}",
          "", "## 检查项" if not errors else "## 检查项（存在错误）"]
    if errors:
        for e in errors:
            md.append(f"- ❌ {e}")
    else:
        md.append("- 章名逐字（01c 顺序）✅")
        md.append("- 占位符零残留 ✅")
        md.append("- 元数据零残留 ✅")
        md.append(f"- 页数闭合：正文 {body} + 证据 {ev_pages} = 总 {total} = PDF 实测 {npages} ✅")
        if meta.get("bid_mode") == "blind":
            md.append(f"- 暗标标识扫描：{len(identities)} 项零命中 ✅")
    if warns:
        md.append("")
        md.append("## 信息态")
        for w in warns:
            md.append(f"- ⚠️ {w}")
    out_p = os.path.join(bid, "07_out", "verify-report.md")
    with open(out_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    if errors:
        print(f"回读校验未通过：{len(errors)} 项错误（见 {out_p}）")
        for e in errors:
            print("  ❌", e)
        return 1
    # 出口：写 stage=exported
    meta["stage"] = "exported"
    meta.setdefault("skill_versions", {})["bid-docx-export"] = _read_version()
    meta["updated_at"] = _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
    with open(os.path.join(bid, "00_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"回读校验通过（报告：{out_p}）")
    for w in warns:  # 信息态不抬 rc，但终端可见（藏报告里易漏看）
        print("  ⚠️", w)
    print()
    print("交付完成：07_out/投标文件.docx、投标文件_含附件.pdf、排版依据说明.md")
    print("提醒：电子标平台上传前请人工核对页数与文件大小上限；另存后再编辑，勿直接改交付件。")
    return 0


def _read_version() -> str:
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
            m = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", f.read(), re.M)
            return m.group(1) if m else "?"
    except OSError:
        return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--identity", default="", help="暗标标识串（逗号分隔）")
    args = ap.parse_args()
    if not os.path.isdir(args.bid):
        print(f"【执行阻断】bid 目录不存在：{args.bid}")
        return 2
    ids = [s.strip() for s in args.identity.split(",") if s.strip()]
    return verify(args.bid, ids)


if __name__ == "__main__":
    sys.exit(main())
