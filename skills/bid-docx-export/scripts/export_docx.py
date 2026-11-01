#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 正文 docx 生成（export_docx.py）
=====================================================
纯标准库（zipfile+XML）生成 07_out/投标文件.docx：
仿宋_GB2312 小四、1.5 倍行距、首行缩进 2 字符（样式档参数化）、
页脚 PAGE 域居中、A4 页边距（样式档）；章名逐字取 01c（铁律 2）；
[[EV:ev-xxx]] 按 07_out/pagination.json 替换为「见附件 A-xx（第N–M页）」；
[[F:]]/[[S:]] 溯源标注剔除（交付稿不出现标注）；
正文插图 ![题注](assets/x.png) 校验 05_chapters/assets/ 源文件存在后嵌入 word/media/
（缺失记 failed_nodes 并输出【待补图：…】占位；暗标剥离 JPEG EXIF）。

⚠️ 插图能力边界：本套件**纯标准库零三方依赖**，故不做像素级重编码/压缩——
只做存在性校验、显示尺寸按版心等比收敛、成品体积机检。压缩请人工完成。

前置：assemble_pdf.py 已跑（读其 pagination.json）。闸门同 assemble。

用法：
  python export_docx.py --bid <bid目录> [--docx-max-mb 50] [--img-max-mb 5]
  rc：0＝生成；1＝错误（含插图缺失/成品超限）；2＝前置缺失/闸门阻断（零产物）。
"""
import argparse
import datetime as _dt
import json
import os
import re
import struct
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


# Markdown 块 → Word 外观渲染（样式层；不改一个字的内容）
TBL_BORDERS = ("<w:tblBorders>"
               '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               "</w:tblBorders>")
TBL_CELL_MAR = ('<w:tblCellMar><w:top w:w="28" w:type="dxa"/><w:left w:w="57" w:type="dxa"/>'
                '<w:bottom w:w="28" w:type="dxa"/><w:right w:w="57" w:type="dxa"/></w:tblCellMar>')
TBL_SEP_RE = re.compile(r"^:?-{2,}:?$")
CAPTION_RE = re.compile(r"^表\s*附?\d+\s*[-–—]\s*\d+")


def rpr_xml(size_pt: float, font: str, bold: bool = False,
            ascii_font: str = "Times New Roman") -> str:
    sz = int(round(size_pt * 2))
    return (f'<w:rPr><w:rFonts w:ascii="{xesc(ascii_font)}" w:hAnsi="{xesc(ascii_font)}" '
            f'w:eastAsia="{xesc(font)}"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
            + ("<w:b/><w:bCs/>" if bold else "") + "</w:rPr>")


def inline_runs(text: str, size_pt: float, font: str, bold: bool = False,
                ascii_font: str = "Times New Roman") -> str:
    """行内文本 → run 序列；`**加粗**` 转真加粗（Markdown 标记不得进交付稿）。"""
    runs = []
    for i, part in enumerate(text.split("**")):
        if not part:
            continue
        runs.append(f'<w:r>{rpr_xml(size_pt, font, bold or i % 2 == 1, ascii_font)}'
                    f'<w:t xml:space="preserve">{xesc(part)}</w:t></w:r>')
    return "".join(runs)


def para_xml(text: str, size_pt: float, line_sp: float, indent_chars: float,
             font: str, bold: bool = False, center: bool = False, heading=None,
             indent: bool = True, page_break: bool = False) -> str:
    line = int(round(240 * line_sp))
    ppr = "<w:pPr>"
    if page_break:
        ppr += "<w:pageBreakBefore/>"
    if heading is not None:
        ppr += f'<w:outlineLvl w:val="{heading}"/>'
    if center:
        ppr += '<w:jc w:val="center"/>'
    ppr += f'<w:spacing w:line="{line}" w:lineRule="auto" w:before="120" w:after="120"/>'
    if indent and not center and not bold and indent_chars > 0:
        ppr += (f'<w:ind w:firstLineChars="{int(round(indent_chars * 100))}" '
                f'w:firstLine="{int(round(size_pt * 20 * indent_chars))}"/>')
    ppr += rpr_xml(size_pt, font, bold) + "</w:pPr>"
    return f"<w:p>{ppr}{inline_runs(text, size_pt, font, bold=bold)}</w:p>"


def code_xml(lines: list, font: str, usable_pt: float) -> str:
    """围栏代码块（含 ASCII 拓扑示意）→ 逐行成段：保留行首空格与行结构；
    西文字体取正文字体（仿宋_GB2312 的半角拉丁），使 ASCII 图与全角字符对齐。"""
    if not lines:
        return ""

    def _w(s: str, sz: float) -> float:
        return sum(sz * (0.5 if ord(c) < 128 else 1.0) for c in s)

    maxw = max([_w(l, 1.0) for l in lines] + [1.0])
    csize = 7.5
    for cand in (10.5, 9.0, 7.5):
        if maxw * cand <= usable_pt:
            csize = cand
            break
    out = []
    for l in lines:
        ppr = ('<w:pPr><w:spacing w:line="240" w:lineRule="auto" w:before="0" w:after="0"/>'
               + rpr_xml(csize, font, False, ascii_font=font) + "</w:pPr>")
        out.append(f"<w:p>{ppr}{inline_runs(l, csize, font, ascii_font=font)}</w:p>")
    return "".join(out)


# ======================= 插图管线（P0-3） =======================
# 契约来源：③ references/图表与题注规范.md §五——「写作层插图 Markdown ![图 3-1 ××](assets/xxx.png)，
# 源文件置 05_chapters/assets/；缺源文件的图 → 保留题注与占位说明【待补图：…】；
# ④ 装配时校验引用文件存在，缺失记 failed_nodes」。本文件兑现该契约。
#
# ⚠️ 能力边界（诚实声明）：本套件坚持**纯标准库零三方依赖**，因此
#    **不做像素级重编码/缩放压缩**（那需要 PIL/Pillow）。本管线做的是：
#    ① 源文件存在性校验（缺失→failed_nodes）；② 按版心等比收敛**显示尺寸**（不改原图字节）；
#    ③ 嵌入 word/media/ + OpenXML drawing；④ 成品体积机检；
#    ⑤ 暗标模式剥离 JPEG 的 EXIF/IPTC 段。超出上述范围的压缩请人工用图像处理工具完成。
IMG_RE = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)\s*\)")
EMU_PER_PX = 9525          # 96 DPI：1 px = 9525 EMU
EMU_PER_PT = 12700         # 1 pt = 12700 EMU
PAGE_H_TWIPS = 16838       # A4 高
IMG_CT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".gif": "image/gif", ".bmp": "image/bmp", ".tif": "image/tiff",
          ".tiff": "image/tiff", ".emf": "image/x-emf", ".wmf": "image/x-wmf"}


def _png_size(b: bytes):
    if len(b) >= 24 and b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    return None


def _jpeg_size(b: bytes):
    i, n = 2, len(b)
    while i < n - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return int(w), int(h)
        if m in (0xD9, 0xDA):
            break
        ln = struct.unpack(">H", b[i + 2:i + 4])[0]
        if ln <= 0:
            break
        i += 2 + ln
    return None


def image_size(path: str):
    """只读文件头解析像素尺寸（PNG/JPEG），**不解码、不依赖三方库**；读不出返回 None。"""
    try:
        with open(path, "rb") as f:
            b = f.read(1 << 16)
    except OSError:
        return None
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return _png_size(b)
    if b[:2] == b"\xff\xd8":
        return _jpeg_size(b)
    return None


def strip_exif(data: bytes) -> bytes:
    """剥离 JPEG 的 APP1/APP2 段（EXIF/IPTC/ICC 可能含作者、相机、软件信息）。

    不重编码、不解码。仅暗标（bid_mode=blind）启用；任一步异常即**原样返回**，
    宁可保留元数据也不损坏图片。
    """
    if data[:2] != b"\xff\xd8":
        return data
    out = bytearray(data[:2])
    i, n = 2, len(data)
    try:
        while i < n - 3:
            if data[i] != 0xFF:
                break
            m = data[i + 1]
            if m in (0xD9, 0xDA):          # EOI / SOS：其后为压缩数据，整体保留
                out += data[i:]
                return bytes(out)
            if m == 0x01 or 0xD0 <= m <= 0xD7:
                out += data[i:i + 2]
                i += 2
                continue
            ln = struct.unpack(">H", data[i + 2:i + 4])[0]
            if ln <= 0:
                break
            seg = data[i:i + 2 + ln]
            if m not in (0xE1, 0xE2):      # 只丢 APP1/APP2
                out += seg
            i += 2 + ln
        out += b"\xff\xd9"
    except Exception:
        return data
    res = bytes(out)
    # 自检：首尾标记必须合法，否则回退原数据（不因清理而损坏图片）
    return res if (res[:2] == b"\xff\xd8" and res[-2:] == b"\xff\xd9") else data


def collect_images(bid: str, chapters: list) -> dict:
    """扫全部章节正文的图片引用 → 校验源文件存在 → 分配 rId / media 部件名。

    返回 ctx = {"map": {引用串: info}, "missing": [引用串], "dir": assets 目录}
    """
    assets_dir = os.path.join(bid, "05_chapters", "assets")
    map_, missing = {}, []
    seq = 0
    for ch in chapters:
        for p in (ch.get("paragraphs") or []):
            for m in IMG_RE.finditer(p or ""):
                rel = m.group(2).strip()
                if rel in map_ or rel in missing:
                    continue
                cand = rel.replace("\\", "/")
                if cand.startswith("assets/"):
                    cand = cand[len("assets/"):]
                abs_p = os.path.normpath(os.path.join(assets_dir, cand))
                if not os.path.isfile(abs_p):
                    missing.append(rel)
                    continue
                seq += 1
                ext = os.path.splitext(abs_p)[1].lower()
                map_[rel] = {"abs": abs_p, "ext": ext, "idx": seq,
                             "rid": f"rId{100 + seq}",
                             "media": f"media/img{seq}{ext}",
                             "size": image_size(abs_p),
                             "bytes": os.path.getsize(abs_p),
                             "name": os.path.basename(abs_p)}
    return {"map": map_, "missing": missing, "dir": assets_dir}


def image_xml(info: dict, max_cx: int, max_cy: int) -> str:
    """图片段（居中，上下留白）；显示尺寸按版心等比收敛，原图字节不动。"""
    w_px, h_px = info.get("size") or (800, 600)
    cx, cy = int(w_px * EMU_PER_PX), int(h_px * EMU_PER_PX)
    if cx > 0 and cy > 0 and (cx > max_cx or cy > max_cy):
        k = min(max_cx / cx, max_cy / cy)
        cx, cy = max(1, int(cx * k)), max(1, int(cy * k))
    i = info["idx"]
    return ('<w:p><w:pPr><w:jc w:val="center"/>'
            '<w:spacing w:line="240" w:lineRule="auto" w:before="60" w:after="60"/></w:pPr>'
            '<w:r><w:drawing>'
            '<wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/>'
            '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{i}" name="图片{i}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic><pic:nvPicPr>'
            f'<pic:cNvPr id="{i}" name="img{i}"/>'
            '<pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill>'
            f'<a:blip r:embed="{info["rid"]}"/>'
            '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def image_blocks(p: str, img_ctx, ev_map, size, lsp, ind, font,
                 total_twips, usable_pt, max_cy) -> list:
    """含图片语法的段 → [题注前文本…, 图片段(+), 图题段(+), 图片后文本…]。

    源文件缺失时按 ③ 规范输出「【待补图：图 3-1 ××】」占位，交人工补图。
    """
    out, pos = [], 0
    map_ = (img_ctx or {}).get("map", {})
    max_cx = int(usable_pt * EMU_PER_PT)
    for m in IMG_RE.finditer(p):
        pre = p[pos:m.start()].strip()
        if pre:
            out.extend(paragraph_blocks(pre, ev_map, size, lsp, ind, font,
                                        total_twips, usable_pt))
        rel, alt = m.group(2).strip(), (m.group(1) or "").strip()
        info = map_.get(rel)
        if info:
            out.append(("para", image_xml(info, max_cx, max_cy)))
            if alt:
                out.append(("para", para_xml(alt, size * 0.9, 1.0, 0, font,
                                             center=True, indent=False)))
        else:
            out.append(("para", para_xml(f"【待补图：{alt or rel}】", size, lsp, 0, font,
                                         center=True, indent=False)))
        pos = m.end()
    tail = p[pos:].strip()
    if tail:
        out.extend(paragraph_blocks(tail, ev_map, size, lsp, ind, font,
                                    total_twips, usable_pt))
    return out


def table_cells(line: str) -> list:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def table_xml(rows: list, size_pt: float, font: str, total_twips: int) -> str:
    """Markdown 管道表 → Word 表格；首行表头（跨页重复），按列数降档字号。"""
    rows = [r for r in rows if r]
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    per = max(1, int(total_twips) // ncol)
    csize = size_pt if ncol <= 4 else (10.5 if ncol <= 7 else 9.0)
    grid = "".join(f'<w:gridCol w:w="{per}"/>' for _ in range(ncol))
    pr = (f'<w:tblPr><w:tblW w:w="{int(total_twips)}" w:type="dxa"/>'
          '<w:tblLayout w:type="fixed"/>' + TBL_BORDERS + TBL_CELL_MAR + "</w:tblPr>")
    trs = []
    for ri, row in enumerate(rows):
        cells = list(row) + [""] * (ncol - len(row))
        trpr = "<w:trPr>" + ("<w:tblHeader/>" if ri == 0 else "") + "</w:trPr>"
        tcs = []
        for c in cells:
            jc = "center" if ri == 0 else "left"
            cppr = ("<w:pPr>"
                    f'<w:jc w:val="{jc}"/>'
                    '<w:spacing w:line="240" w:lineRule="auto" w:before="20" w:after="20"/>'
                    + rpr_xml(csize, font, ri == 0) + "</w:pPr>")
            tcs.append(f'<w:tc><w:tcPr><w:tcW w:w="{per}" w:type="dxa"/>'
                       f'<w:vAlign w:val="center"/></w:tcPr><w:p>{cppr}'
                       f"{inline_runs(c, csize, font, bold=(ri == 0))}</w:p></w:tc>")
        trs.append(f"<w:tr>{trpr}{''.join(tcs)}</w:tr>")
    return f'<w:tbl>{pr}<w:tblGrid>{grid}</w:tblGrid>{"".join(trs)}</w:tbl>'


def paragraph_blocks(p: str, ev_map: dict, size: float, lsp: float, ind: float,
                     font: str, total_twips: int, usable_pt: float,
                     img_ctx=None, max_cy: int = 0) -> list:
    """正文段（Markdown 块）→ [(kind, xml)]，kind ∈ {'para','table'}。

    ④ 只改外观：管道表→w:tbl、`**加粗**`→真加粗、多行块逐行成段，
    文本内容一字不动（并入的只剩排版语义）。
    含 `![题注](assets/x.png)` 时走插图管线（P0-3），见 image_blocks。
    """
    p = _common.replace_ev(p, ev_map)
    if "![" in p and IMG_RE.search(p):
        return image_blocks(p, img_ctx, ev_map, size, lsp, ind, font,
                            total_twips, usable_pt, max_cy)
    lines = p.split("\n")
    nonempty = [l for l in lines if l.strip()]
    if not nonempty:
        return []
    # 1) 围栏代码块（正文含空行时一个围栏会被拆成两段，首/末行各带 ``` 标记）
    if any(l.strip().startswith("```") for l in lines):
        xml = code_xml([l for l in lines if not l.strip().startswith("```")], font, usable_pt)
        return [("para", xml)] if xml else []
    # 2) 表格块（表题与表同段时，题注行在前、管道表在后）
    tbl = [i for i, l in enumerate(nonempty) if l.strip().startswith("|")]
    if tbl:
        blocks = [("para", para_xml(hl.strip(), size, lsp, ind, font))
                  for hl in nonempty[:tbl[0]]]
        rows = []
        for l in nonempty[tbl[0]:]:
            cells = table_cells(l)
            if cells and all(TBL_SEP_RE.match(c) for c in cells if c != ""):
                if all(TBL_SEP_RE.match(c) for c in cells):
                    continue
            rows.append(cells)
        if rows:
            blocks.append(("table", table_xml(rows, size, font, total_twips)))
        return blocks
    # 3) 多行块（引用块 / 无序·有序列表 / 落款行）→ 逐行成段，不首行缩进
    if len(nonempty) > 1:
        blocks = []
        for l in lines:
            t = re.sub(r"^\s*>\s?", "", l).strip()
            t = re.sub(r"^[-*+]\s+", "", t).strip()
            if t:
                blocks.append(("para", para_xml(t, size, lsp, ind, font, indent=False)))
        return blocks
    # 4) 单行段（标题 / 图表题注 / 正文）
    t = re.sub(r"^\s*>\s?", "", nonempty[0].strip()).strip()
    if t.startswith("#### "):
        return [("para", para_xml(t[5:], size * 1.05, lsp, ind, font, bold=True, heading=3))]
    if t.startswith("### "):
        return [("para", para_xml(t[4:], size * 1.1, lsp, ind, font, bold=True, heading=2))]
    if t.startswith("## "):
        return [("para", para_xml(t[3:], size * 1.15, lsp, ind, font, bold=True, heading=1))]
    if t.startswith("# "):
        return [("para", para_xml(t[2:], size * 1.2, lsp, ind, font, bold=True,
                                  center=True, heading=0))]
    if CAPTION_RE.match(t):
        return [("para", para_xml(t, size, lsp, ind, font, bold=True, indent=False))]
    return [("para", para_xml(t, size, lsp, ind, font))]


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


def build_document(chapters, style, ev_map, title: str, img_ctx=None) -> str:
    t = style.get("typography", {})
    size = float(t.get("size_body_pt", 12))
    lsp = float(t.get("line_spacing", 1.5))
    ind = float(t.get("first_line_indent_chars", 2))
    font = t.get("font_body", "仿宋_GB2312")
    mg = t.get("margins_cm", {})
    pn_mode = str(t.get("page_number", "footer_center"))
    pn_parts, _jcs, pn_refs = PN_MODES.get(pn_mode, PN_MODES["footer_center"])
    left = float(mg.get("left", 3.17))
    right = float(mg.get("right", 3.17))
    total_twips = 11906 - int(round(left * 567)) - int(round(right * 567))
    usable_pt = total_twips / 20.0
    # 插图最大高度：版心净高 ×0.85（留出题注与段间距），防止单图占满整页
    _top = float(mg.get("top", 2.54))
    _bot = float(mg.get("bottom", 2.54))
    usable_h_pt = max(120.0, (PAGE_H_TWIPS - int(round(_top * 567)) - int(round(_bot * 567))) / 20.0)
    max_cy = int(usable_h_pt * 0.85 * EMU_PER_PT)
    blocks = []
    for ci, ch in enumerate(chapters):
        lvl = ch.get("level", 2)
        num = str(ch.get("number") or "").strip()
        head = f"{num}　{ch['title']}" if num else str(ch["title"])
        if lvl <= 2:
            blocks.append(("para", para_xml(head, size * 1.33, lsp, 0, font,
                                            bold=True, center=True, heading=0,
                                            page_break=(ci > 0))))
        else:
            blocks.append(("para", para_xml(head, size * 1.15, lsp, 0, font,
                                            bold=True, heading=min(lvl - 2, 6),
                                            page_break=(ci > 0))))
        for p in ch["paragraphs"]:
            blocks.extend(paragraph_blocks(p, ev_map, size, lsp, ind, font,
                                           total_twips, usable_pt,
                                           img_ctx=img_ctx, max_cy=max_cy))
    # Word 硬性要求：相邻两表若不以段落分隔会被合并为一个表；表格位于文档末尾亦须补空段。
    body = []
    for i, (kind, xml) in enumerate(blocks):
        if not xml:
            continue
        body.append(xml)
        nxt_is_table = (i + 1 < len(blocks) and blocks[i + 1][0] == "table")
        if kind == "table" and (nxt_is_table or i == len(blocks) - 1):
            body.append("<w:p/>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<w:body>' + "".join(body) + sect_xml(mg, pn_refs) + "</w:body></w:document>")


def export(bid: str, docx_max_mb: float = 50.0, img_max_mb: float = 5.0) -> int:
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
    # —— 插图管线：先扫描并校验源文件（缺失记 failed_nodes，兑现 ③ §五契约）——
    img_ctx = collect_images(bid, chapters)
    img_missing = img_ctx["missing"]
    blind = str(meta.get("bid_mode", "")).strip() == "blind"
    if img_missing:
        print(f"❌ 插图源文件缺失 {len(img_missing)} 项（未在 {img_ctx['dir']} 下找到）：")
        for r in img_missing:
            print("   - " + r)
        print("   处置：补齐源文件后重导；本次按 ③ 规范输出【待补图：…】占位，交人工补图")
        meta.setdefault("failed_nodes", [])
        for r in img_missing:
            node = f"missing_image:{r}"
            if node not in meta["failed_nodes"]:
                meta["failed_nodes"].append(node)
        _common.persist_failed_nodes(bid, meta)
    doc_xml = build_document(chapters, style, ev_map, title, img_ctx=img_ctx)
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
    for _ext in sorted({v["ext"] for v in img_ctx["map"].values()}):
        _ct = IMG_CT.get(_ext)
        if _ct:
            ct_lines.append(f'<Default Extension="{_ext.lstrip(".")}" ContentType="{_ct}"/>')
        else:
            print(f"⚠️ 未登记的图片扩展名 {_ext}，未写 Content-Type（该图可能打不开）："
                  f"{[v['name'] for v in img_ctx['map'].values() if v['ext'] == _ext]}")
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
    for _rel, info in img_ctx["map"].items():
        rel_lines.append(f'<Relationship Id="{info["rid"]}" Type="http://schemas.openxmlformats.org/'
                         f'officeDocument/2006/relationships/image" Target="{info["media"]}"/>')
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
        for _rel, info in img_ctx["map"].items():
            try:
                with open(info["abs"], "rb") as f:
                    data = f.read()
            except OSError as e:
                print(f"⚠️ 图片读取失败，已跳过：{info['abs']}（{e}）")
                continue
            if blind and info["ext"] in (".jpg", ".jpeg"):
                cleaned = strip_exif(data)
                if len(cleaned) != len(data):
                    print(f"   暗标：已剥离 JPEG 元数据段「{info['name']}」"
                          f"（{len(data)} → {len(cleaned)} 字节）")
                data = cleaned
            elif blind and info["ext"] == ".png":
                print(f"⚠️ 暗标：PNG「{info['name']}」可能含 tEXt 文本元数据；"
                      "本套件不做 PNG 元数据清理，请人工确认")
            z.writestr("word/" + info["media"], data)
        z.writestr("word/settings.xml", SETTINGS.rstrip("</w:settings>") + pn_settings_extra(pn_mode) + "</w:settings>")

    n_ev = len(ev_map)
    n_img = len(img_ctx["map"])
    size_mb = os.path.getsize(out_p) / (1024.0 * 1024.0)
    img_mb = sum(v["bytes"] for v in img_ctx["map"].values()) / (1024.0 * 1024.0)
    print(f"docx 已生成：{out_p}（{size_mb:.2f} MB）")
    print(f"章节 {len(chapters)} 个；页码档位 {pn_mode}；[[EV:]] 已替换 {n_ev} 处映射（未映射引用保留原样待查）")
    if n_img:
        print(f"插图 {n_img} 张（源文件合计 {img_mb:.2f} MB）已嵌入 word/media/")
    # 体积机检：单张告警 + 成品超限须处置（电子标平台常见 50/100MB 上传上限）
    big = [v["name"] for v in img_ctx["map"].values() if v["bytes"] > img_max_mb * 1024 * 1024]
    if big:
        print(f"⚠️ 单张图片超 {img_max_mb} MB：{'、'.join(big)}"
              "（本套件零三方依赖，不做重编码压缩，请人工压缩后重导）")
    if size_mb > docx_max_mb:
        print(f"❌ 成品 {size_mb:.2f} MB 超上限 {docx_max_mb} MB（电子标平台常见上传限制）"
              "——处置：压缩插图或拆分附件后重导")
        return 1
    if img_missing:
        print(f"❌ 插图源文件缺失 {len(img_missing)} 项，已记 failed_nodes；"
              "本次以【待补图：…】占位输出，补齐后须重导")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--docx-max-mb", type=float, default=50.0,
                    help="成品 docx 体积上限 MB，超限 rc=1（默认 50，电子标平台常见上传限制）")
    ap.add_argument("--img-max-mb", type=float, default=5.0,
                    help="单张插图告警阈值 MB（默认 5；只告警不阻断，压缩需人工完成）")
    args = ap.parse_args()
    if not os.path.isdir(args.bid):
        print(f"【执行阻断】bid 目录不存在：{args.bid}")
        return 2
    return export(args.bid, docx_max_mb=args.docx_max_mb, img_max_mb=args.img_max_mb)


if __name__ == "__main__":
    sys.exit(main())
