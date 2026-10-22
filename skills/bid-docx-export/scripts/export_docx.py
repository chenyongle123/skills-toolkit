#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 正文 docx 生成（export_docx.py）
=====================================================
纯标准库（zipfile+XML）生成 07_out/投标文件.docx：
仿宋_GB2312 小四、1.5 倍行距、首行缩进 2 字符（样式档参数化）、
页脚 PAGE 域居中、A4 页边距（样式档）；章名逐字取 01c（铁律 2）；
[[EV:ev-xxx]] 按 07_out/pagination.json 替换为「见附件 A-xx（第N–M页）」；
[[F:]]/[[S:]] 溯源标注剔除（交付稿不出现标注）。

前置：assemble_pdf.py 已跑（读其 pagination.json）。闸门同 assemble。

用法：
  python export_docx.py --bid <bid目录>
  rc：0＝生成；1＝错误；2＝前置缺失/闸门阻断（零产物）。
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

CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="FangSong_GB2312" w:cs="Times New Roman"/>
<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/>
</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>
<w:widowControl/><w:jc w:val="both"/>
</w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>
<w:qFormat/></w:style>
</w:styles>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>"""

def _hf_xml(tag: str, jc: str) -> str:
    """页眉/页脚部件 XML（tag=ftr|hdr；jc=居中/右/左）；页码字号 9pt。"""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:{tag} xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:p><w:pPr><w:jc w:val="{jc}"/>'
            '<w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="FangSong_GB2312"/>'
            '<w:sz w:val="18"/></w:rPr></w:pPr>'
            '<w:fldSimple w:instr=" PAGE "><w:r><w:rPr><w:sz w:val="18"/></w:rPr>'
            '<w:t>1</w:t></w:r></w:fldSimple>'
            '</w:p></w:%s>' % tag)


# 页码档位 → (部件名列表, 每部件对齐, sect 引用, settings 附加)。
# 档位定义 build_style_profile.parse_page_number（none/header_center/footer_center/footer_outer）。
PN_MODES = {
    "none":          ([], [], ""),
    "header_center": (["word/header1.xml"], ["center"],
                      '<w:headerReference w:type="default" r:id="rId4"/>'),
    "footer_center": (["word/footer1.xml"], ["center"],
                      '<w:footerReference w:type="default" r:id="rId2"/>'),
    "footer_outer":  (["word/footer1.xml", "word/footer2.xml"], ["right", "left"],
                      '<w:footerReference w:type="default" r:id="rId2"/>'
                      '<w:footerReference w:type="even" r:id="rId4"/>'),
}


def pn_settings_extra(pn_mode: str) -> str:
    """footer_outer 需 evenAndOddHeaders（奇偶分侧页码）。"""
    return "<w:evenAndOddHeaders/>" if pn_mode == "footer_outer" else ""

SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:zoom w:percent="100"/>
</w:settings>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{title}</dc:title>
<dc:creator></dc:creator><cp:lastModifiedBy></cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">{t}</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">{t}</dcterms:modified>
</cp:coreProperties>"""

APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Application>Microsoft Office Word</Application>
</Properties>"""


def xesc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def para_xml(text: str, size_pt: float, line_sp: float, indent_chars: float,
             font: str, bold: bool = False, center: bool = False, heading=None) -> str:
    sz = int(round(size_pt * 2))
    rpr = (f'<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
           f'w:eastAsia="{xesc(font)}"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
           + ("<w:b/><w:bCs/>" if bold else "") + "</w:rPr>")
    line = int(round(240 * line_sp))
    ppr = "<w:pPr>"
    if heading is not None:
        ppr += f'<w:outlineLvl w:val="{heading}"/>'
    if center:
        ppr += '<w:jc w:val="center"/>'
    ppr += f'<w:spacing w:line="{line}" w:lineRule="auto" w:before="120" w:after="120"/>'
    if not center and not bold and indent_chars > 0:
        ppr += (f'<w:ind w:firstLineChars="{int(round(indent_chars * 100))}" '
                f'w:firstLine="{int(round(size_pt * 20 * indent_chars))}"/>')
    ppr += rpr + "</w:pPr>"
    run = f'<w:r>{rpr}<w:t xml:space="preserve">{xesc(text)}</w:t></w:r>'
    return f"<w:p>{ppr}{run}</w:p>"


def sect_xml(margins_cm: dict, pn_refs: str = "") -> str:
    def tw(cm):
        return int(round(cm * 567))
    return ('<w:sectPr>' + pn_refs +
            '<w:pgSz w:w="11906" w:h="16838"/>'
            f'<w:pgMar w:top="{tw(margins_cm.get("top", 2.54))}" '
            f'w:right="{tw(margins_cm.get("right", 3.17))}" '
            f'w:bottom="{tw(margins_cm.get("bottom", 2.54))}" '
            f'w:left="{tw(margins_cm.get("left", 3.17))}" '
            'w:header="851" w:footer="992" w:gutter="0"/>'
            '<w:cols w:space="425"/><w:docGrid w:type="lines" w:linePitch="312"/></w:sectPr>')


def replace_ev(text: str, ev_map: dict) -> str:
    """[[EV:ev-xxx]] → 见附件A-xx（第N–M页）（实装见 _common.replace_ev，此处转发保持旧调用兼容）。"""
    return _common.replace_ev(text, ev_map)


def build_document(chapters, style, ev_map, title: str) -> str:
    t = style.get("typography", {})
    size = float(t.get("size_body_pt", 12))
    lsp = float(t.get("line_spacing", 1.5))
    ind = float(t.get("first_line_indent_chars", 2))
    font = t.get("font_body", "仿宋_GB2312")
    mg = t.get("margins_cm", {})
    pn_mode = str(t.get("page_number", "footer_center"))
    pn_parts, _jcs, pn_refs = PN_MODES.get(pn_mode, PN_MODES["footer_center"])
    body = []
    for ch in chapters:
        lvl = ch.get("level", 2)
        head = f"{ch['number']}　{ch['title']}"
        if lvl <= 2:
            body.append(para_xml(head, size * 1.33, lsp, 0, font, bold=True, center=True, heading=0))
        else:
            body.append(para_xml(head, size * 1.15, lsp, 0, font, bold=True, heading=min(lvl - 2, 6)))
        for p in ch["paragraphs"]:
            p = _common.replace_ev(p, ev_map)
            if p.startswith("#### "):
                body.append(para_xml(p[5:], size * 1.05, lsp, ind, font, bold=True, heading=3))
            elif p.startswith("### "):
                body.append(para_xml(p[4:], size * 1.1, lsp, ind, font, bold=True, heading=2))
            elif p.startswith("## "):
                body.append(para_xml(p[3:], size * 1.15, lsp, ind, font, bold=True, heading=1))
            elif p.startswith("# "):
                body.append(para_xml(p[2:], size * 1.2, lsp, ind, font, bold=True, center=True, heading=0))
            else:
                body.append(para_xml(p, size, lsp, ind, font))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<w:body>' + "".join(body) + sect_xml(mg, pn_refs) + "</w:body></w:document>")


def export(bid: str) -> int:
    rc, msgs, meta = _common.gate(bid)
    for m in msgs:
        print(m)
    if rc != 0:
        _common.persist_failed_nodes(bid, meta)
        return rc
    out_dir = os.path.join(bid, "07_out")
    pag_p = os.path.join(out_dir, "pagination.json")
    if not os.path.exists(pag_p):
        print("【执行阻断】07_out/pagination.json 缺失（先运行 assemble_pdf.py）")
        return 2
    pag = json.load(open(pag_p, encoding="utf-8"))
    idx_p = os.path.join(bid, "03b_evidence-index.json")
    if not os.path.exists(idx_p):
        print("【执行阻断】03b_evidence-index.json 缺失（先运行 index_evidence.py）")
        return 2
    idx = json.load(open(idx_p, encoding="utf-8"))
    # [[EV:]] 替换表：id → (起始页, 结束页, 附件号)
    ev_map = {}
    by_id = {it["id"]: it for it in idx.get("items", [])}
    for ev in pag.get("evidence", []):
        it = by_id.get(ev.get("id", ""))
        if it:
            ev_map[ev["id"]] = (ev["start_page"], ev["start_page"] + ev["pages"] - 1, it.get("attach_no", ""))

    style = _common.read_style_profile(bid)
    if not style:
        print("【执行阻断】07_out/style-profile.yaml 缺失（先运行 build_style_profile.py）")
        return 2
    outline = json.load(open(os.path.join(bid, "01c_format-outline.json"), encoding="utf-8"))
    chapters = []
    for ch in _common.load_chapters_sorted(bid, outline):
        chapters.append({"id": ch["id"], "number": ch["number"], "title": ch["title"],
                         "level": ch.get("level", 2),
                         "paragraphs": [p for p in ch["paragraphs"] if p]})
    if not chapters:
        print("【执行阻断】05_chapters 按 01c 章序装载为空（章节文件缺或 chapter_id 不匹配）")
        return 2

    title = str(meta.get("project", {}).get("name", "投标文件"))
    now = _dt.datetime.now().replace(microsecond=0).isoformat()
    doc_xml = build_document(chapters, style, ev_map, title)
    core = CORE.format(title=xesc(title), t=now)
    # 页码档位部件（CT/rels 按 PN_MODES 动态组装；none 不写页码部件）
    t_style = style.get("typography", {})
    pn_mode = str(t_style.get("page_number", "footer_center"))
    pn_parts, pn_jcs, _refs = PN_MODES.get(pn_mode, PN_MODES["footer_center"])
    ct_lines = [CT.rstrip("</Types>")]
    for part, jc in zip(pn_parts, pn_jcs):
        tag = "footer" if part.startswith("word/footer") else "header"
        ct_lines.append(f'<Override PartName="/{part}" ContentType="application/vnd.openxmlformats-'
                        f'officedocument.wordprocessingml.{tag}+xml"/>')
    ct_lines.append("</Types>")
    rel_lines = [DOC_RELS.rstrip("</Relationships>")]
    if "word/footer1.xml" in pn_parts:
        rel_lines.append('<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
                         'officeDocument/2006/relationships/footer" Target="footer1.xml"/>')
    if "word/header1.xml" in pn_parts:
        rel_lines.append('<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/'
                         'officeDocument/2006/relationships/header" Target="header1.xml"/>')
    if pn_mode == "footer_outer":
        rel_lines.append('<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/'
                         'officeDocument/2006/relationships/footer" Target="footer2.xml"/>')
    rel_lines.append("</Relationships>")
    out_p = os.path.join(out_dir, "投标文件.docx")
    with zipfile.ZipFile(out_p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct_lines))
        z.writestr("_rels/.rels", RELS)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", APP)
        z.writestr("word/document.xml", doc_xml)
        z.writestr("word/_rels/document.xml.rels", "".join(rel_lines))
        z.writestr("word/styles.xml", STYLES)
        for part, jc in zip(pn_parts, pn_jcs):
            tag = "ftr" if part.startswith("word/footer") else "hdr"
            z.writestr(part, _hf_xml(tag, jc))
        z.writestr("word/settings.xml", SETTINGS.rstrip("</w:settings>") + pn_settings_extra(pn_mode) + "</w:settings>")

    n_ev = len(ev_map)
    print(f"docx 已生成：{out_p}")
    print(f"章节 {len(chapters)} 个；页码档位 {pn_mode}；[[EV:]] 已替换 {n_ev} 处映射（未映射引用保留原样待查）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    if not os.path.isdir(args.bid):
        print(f"【执行阻断】bid 目录不存在：{args.bid}")
        return 2
    return export(args.bid)


if __name__ == "__main__":
    sys.exit(main())
