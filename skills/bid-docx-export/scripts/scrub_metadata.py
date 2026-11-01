#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 元数据清理（scrub_metadata.py，计划书 §8.6.3）
==================================================================
普通标与暗标两套口径：
  两种标都清：creator / lastModifiedBy / company / 模板路径（attachedTemplate）
  / 打印机名（lastPrinted）/ 自定义属性（custom.xml）/ 批注（comments）。
  普通标：页眉页脚单位名保留；暗标：另扫页眉页脚与正文的投标人标识串
  （--identity 提供，报事实态不改正文，改正文归 ③）。
修订记录（w:ins/w:del）不自动接受（会改内容）：存在即报，须人工接受后重导。

用法：
  python scrub_metadata.py --bid <bid目录> [--mode normal|blind] [--identity "公司名,人名"]
  rc：0＝清洁完成或已清洁；1＝存在须处置残留（暗标标识命中/修订记录）；
  2＝前置缺失。
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile

DOCX = "07_out/投标文件.docx"
PDF = "07_out/投标文件_含附件.pdf"


def _sub_desc(data: bytes) -> bytes:
    xml = data.decode("utf-8")
    xml = re.sub(r"<dc:creator>.*?</dc:creator>", "<dc:creator/>", xml, flags=re.S)
    xml = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy/>", xml, flags=re.S)
    xml = re.sub(r"<cp:lastPrinted>.*?</cp:lastPrinted>", "", xml, flags=re.S)
    xml = re.sub(r"<dc:description>.*?</dc:description>", "", xml, flags=re.S)
    xml = re.sub(r"<dc:subject>.*?</dc:subject>", "", xml, flags=re.S)
    xml = re.sub(r"<cp:keywords>.*?</cp:keywords>", "", xml, flags=re.S)
    return xml.encode("utf-8")


def _sub_app(data: bytes) -> bytes:
    xml = data.decode("utf-8")
    xml = re.sub(r"<Company>.*?</Company>", "", xml, flags=re.S)
    xml = re.sub(r"<Manager>.*?</Manager>", "", xml, flags=re.S)
    xml = re.sub(r"<Template>.*?</Template>", "", xml, flags=re.S)
    return xml.encode("utf-8")


def _sub_settings(data: bytes) -> bytes:
    xml = data.decode("utf-8")
    xml = re.sub(r"<w:attachedTemplate[^>]*/>", "", xml)
    xml = re.sub(r"<w:attachedTemplate.*?</w:attachedTemplate>", "", xml, flags=re.S)
    xml = re.sub(r"<w:rsids>.*?</w:rsids>", "", xml, flags=re.S)
    return xml.encode("utf-8")


DROP_PARTS = {
    "docProps/custom.xml",
    "docProps/_rels/custom.xml.rels",
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/_rels/comments.xml.rels",
    "word/people.xml",
}


def scrub_docx(path: str) -> list:
    """zip 重写清元数据。返回报告行（含须人工处置项）。"""
    notes = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        parts = {n: z.read(n) for n in names}
        ct = parts["[Content_Types].xml"].decode("utf-8")
        for drop in DROP_PARTS:
            if drop in parts:
                for n in (drop, drop.replace("_rels/", "")):
                    pass
                del parts[drop]
                ct = re.sub(r'<Override PartName="/%s"[^>]*/>' % re.escape(drop), "", ct)
                notes.append(f"已删除部件：{drop}")
        rels = parts.get("_rels/.rels", b"").decode("utf-8")
        rels = re.sub(r'<Relationship [^>]*Target="docProps/custom\.xml"[^>]*/>', "", rels)
        parts["_rels/.rels"] = rels.encode("utf-8")
        if "docProps/core.xml" in parts:
            parts["docProps/core.xml"] = _sub_desc(parts["docProps/core.xml"])
        if "docProps/app.xml" in parts:
            parts["docProps/app.xml"] = _sub_app(parts["docProps/app.xml"])
        if "word/settings.xml" in parts:
            parts["word/settings.xml"] = _sub_settings(parts["word/settings.xml"])
        parts["[Content_Types].xml"] = ct.encode("utf-8")
        # 修订记录检测（不自动接受）
        doc = parts.get("word/document.xml", b"").decode("utf-8", "ignore")
        n_ins = len(re.findall(r"<w:ins\b", doc))
        n_del = len(re.findall(r"<w:del\b", doc))
        if n_ins or n_del:
            notes.append(f"⚠️ 存在未接受修订记录（w:ins×{n_ins}/w:del×{n_del}）：须人工在 Word 接受全部修订后重导，脚本不自动改内容")
        # 批注引用清理（commentRangeStart 等引用残留随 comments.xml 删除）
        if n_ins or n_del or "word/comments.xml" in names:
            doc2 = re.sub(r"<w:commentReference [^>]*/>", "", doc)
            if doc2 != doc:
                parts["word/document.xml"] = doc2.encode("utf-8")

    fd, tmp = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)
    shutil.move(tmp, path)
    return notes


def scrub_pdf(path: str) -> list:
    """trailer /Info 清空：对象级重建（/Info 体换空 dict，全文件对象偏移重算）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pdfutil
    try:
        d = pdfutil.load_pdf(path)
    except pdfutil.PdfError as e:
        return [f"⚠️ PDF 解析失败（跳过 Info 清理）：{e}"]
    info_ref = d.get("trailer", {}).get("Info")
    if not info_ref:
        return ["PDF 无 /Info（已清洁）"]
    m = re.match(rb"(\d+)", info_ref if isinstance(info_ref, bytes) else str(info_ref).encode())
    if not m:
        return ["PDF /Info 引用异常（跳过）"]
    num = int(m.group(1))
    objects = dict(d["objects"])
    if num not in objects:
        return ["PDF /Info 对象不在对象表（跳过）"]
    if b"stream" in objects[num]:
        return ["PDF /Info 含流（异常，跳过）"]
    objects[num] = b"<< >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    root_ref = d.get("trailer", {}).get("Root")
    rm = re.match(rb"(\d+)", root_ref if isinstance(root_ref, bytes) else str(root_ref or b"").encode())
    if not rm:
        return ["PDF /Root 引用异常（跳过）"]
    root = int(rm.group(1))
    for n in sorted(objects):
        offsets[n] = len(out)
        out += f"{n} 0 obj\n".encode() + objects[n] + b"\nendobj\n"
    xref_off = len(out)
    size = max(objects) + 1
    out += b"xref\n0 " + str(size).encode() + b"\n" + b"0000000000 65535 f \n"
    for n in range(1, size):
        if n in offsets:
            out += f"{offsets[n]:010d} 00000 n \n".encode()
        else:
            out += b"0000000000 00000 f \n"
    out += (b"trailer\n<< /Size " + str(size).encode()
            + b" /Root " + str(root).encode() + b" 0 R >>\nstartxref\n"
            + str(xref_off).encode() + b"\n%%EOF\n")
    with open(path, "wb") as f:
        f.write(bytes(out))
    return ["PDF /Info 已清空（Title/Author/Producer 等，对象级重建）"]


def scan_identity(bid: str, identities: list) -> list:
    """暗标：扫页眉页脚/正文/属性中的投标人标识串（报事实态，不改正文）。"""
    hits = []
    dx = os.path.join(bid, DOCX)
    with zipfile.ZipFile(dx) as z:
        targets = {}
        for n in z.namelist():
            if n == "word/document.xml" or re.match(r"word/(header|footer)\d*\.xml$", n):
                targets[n] = z.read(n).decode("utf-8", "ignore")
            if n.startswith("docProps/"):
                targets[n] = z.read(n).decode("utf-8", "ignore")
        for name, xml in targets.items():
            text = re.sub(r"<[^>]+>", "", xml)
            for ident in identities:
                if ident and ident in text:
                    where = "页眉页脚" if re.match(r"word/(header|footer)", name) else ("文档属性" if name.startswith("docProps") else "正文")
                    hits.append(f"暗标标识命中[{where}] {name}：{ident}")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--mode", choices=["normal", "blind"], default=None, help="缺省读 metadata.bid_mode")
    ap.add_argument("--identity", default="", help="投标人标识串（逗号分隔：公司名/人名等）")
    args = ap.parse_args()
    if not os.path.isdir(args.bid):
        print(f"【执行阻断】bid 目录不存在：{args.bid}")
        return 2
    dx = os.path.join(args.bid, DOCX)
    if not os.path.exists(dx):
        print("【执行阻断】bid-docx-export 元数据清理未执行")
        print(f"原因：{dx} 缺失（先运行 assemble_pdf.py + export_docx.py）")
        return 2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _common
    grc, gmsgs, _gmeta = _common.gate(args.bid)  # F8：出口脚本不旁路闸门
    if grc != 0:
        print("【执行阻断】bid-docx-export 元数据清理未执行")
        for m in gmsgs:
            print("  " + m)
        print("处置：先闭环闸门问题（见上）后再清理")
        return 2
    for m in gmsgs:
        print("⚠️", m)
    import json
    meta = json.load(open(os.path.join(args.bid, "00_metadata.json"), encoding="utf-8"))
    mode = args.mode or meta.get("bid_mode", "normal")
    print(f"元数据清理（{mode}）：{dx}")
    notes = scrub_docx(dx)
    for n in notes:
        print(" ", n)
    rc = 1 if any(n.startswith("⚠️") for n in notes) else 0
    pdf_p = os.path.join(args.bid, PDF)
    if os.path.exists(pdf_p):
        for n in scrub_pdf(pdf_p):
            print(" ", n)
    if mode == "blind":
        identities = [s.strip() for s in args.identity.split(",") if s.strip()]
        if not identities:
            print("⚠️ 暗标模式未提供 --identity：标识扫描跳过（建议提供公司名/法人/拟任项目经理姓名）")
        else:
            hits = scan_identity(args.bid, identities)
            pdf_p = os.path.join(args.bid, PDF)
            if os.path.exists(pdf_p):
                for ident in _common.pdf_identity_hits(pdf_p, identities):
                    hits.append(f"暗标标识命中[PDF文本层] 投标文件_含附件.pdf：{ident}")
            for h in hits:
                print("❌", h)
            if hits:
                print("处置：正文/页眉页脚的标识内容修改归 ③（改 md 后重导）；文档属性残留重跑本脚本")
                rc = 1
            else:
                print(f"暗标标识扫描：{len(identities)} 项标识，零命中 ✅")
    else:
        print("普通标：页眉页脚单位名保留（§8.6.3）")
    print("元数据清理完成" + ("（存在须处置项）" if rc else " ✅"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
