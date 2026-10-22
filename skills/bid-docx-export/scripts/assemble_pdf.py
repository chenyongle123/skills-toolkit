#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 合订 PDF 装配（assemble_pdf.py）
=====================================================
正文排版（纯标准库极简 PDF writer：A4/样式档参数/CJK 折行/页码/目录两遍法）
＋ 证据合并（pdfutil 对象级合并，重编号+Pages 树重建）
→ 07_out/投标文件_含附件.pdf ＋ 07_out/pagination.json。

装配顺序（计划书 §8.5.4）：定章节顺序 → 排正文 → 目录页 → 合并证据 →
统一连续页码。总页数 = 正文 + 证据（pagination.json 自证，verify 复核）。
字体：非嵌入 CIDFont Type0 / STSong-Light / UniGB-UCS2-H（PDF 规范内置
中文方案，Acrobat/WPS 可渲染；页数/结构是机检重点，渲染效果人检）。

用法：
  python assemble_pdf.py --bid <bid目录>
  rc：0＝生成；1＝装配错误；2＝前置缺失/闸门阻断（零产物）。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdfutil
import _common

A4_W, A4_H = 595.28, 841.89
PT_PER_CM = 28.3465


def esc(s: str) -> str:
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def text_hex(s: str) -> str:
    """字符串 → UCS2-BE hex（UniGB-UCS2-H 编码）。"""
    return s.encode("utf-16-be").hex().upper()


def char_w(ch: str, size: float) -> float:
    if ord(ch) < 128:
        return size * 0.5
    if 0xFF00 <= ord(ch) <= 0xFFEF or 0x3000 <= ord(ch) <= 0x303F:
        return size
    return size


NO_LINE_HEAD = set("，。、；：？！%）》」』】〕…—·,.;:?!)>]}\"'")


def wrap(text: str, size: float, width: float, indent: float) -> list[str]:
    """逐字累加折行；首行含缩进；避头标点提前折行。"""
    lines = []
    cur = indent
    buf = ""
    pending = ""
    for ch in text:
        w = char_w(ch, size)
        if cur + w > width and buf:
            if ch in NO_LINE_HEAD and cur + w <= width + size * 0.6:
                buf += ch
                cur += w
                continue
            lines.append(buf)
            buf = "" if ch == " " else ch
            cur = char_w(ch, size) if ch != " " else 0
        else:
            buf += ch
            cur += w
    if buf:
        lines.append(buf)
    return lines or [""]


class PageBuf:
    """单页绘制缓冲：累积文本绘制操作，render() 输出该页内容流。"""

    def __init__(self):
        self.ops = []

    def text_at(self, x, y, s, size, bold=False, font="F1"):
        tr = "2 Tr 0.35 w " if bold else "0 Tr "
        self.ops.append(
            f"BT /{font} {size:g} Tf {tr}{x:.2f} {y:.2f} Td <{text_hex(s)}> Tj ET")

    def render(self):
        return "\n".join(self.ops)


class BodyWriter:
    """正文排版器：按样式档参数把章节排成 A4 页面缓冲序列。

    两遍法（计划书 §8.5.4）：pass1 排章节得各章相对起始页 rel（ch_pages 内序）；
    目录页数 K 以估算值起步迭代收敛，章绝对起始页 abs = K + rel。
    """

    def __init__(self, style, chapters):
        t = style.get("typography", {})
        self.size = float(t.get("size_body_pt", 12))
        self.line_sp = float(t.get("line_spacing", 1.5))
        self.line_h = self.size * self.line_sp
        mg = t.get("margins_cm", {})
        self.mL = float(mg.get("left", 3.17)) * PT_PER_CM
        self.mR = float(mg.get("right", 3.17)) * PT_PER_CM
        self.mT = float(mg.get("top", 2.54)) * PT_PER_CM
        self.mB = float(mg.get("bottom", 2.54)) * PT_PER_CM
        self.indent = float(t.get("first_line_indent_chars", 2)) * self.size
        self.width = A4_W - self.mL - self.mR
        self.chapters = chapters
        self.toc_pages: list[PageBuf] = []
        self.ch_pages: list[PageBuf] = []
        self._target = None
        self.y = 0.0

    def _new_page(self):
        pg = PageBuf()
        self._target.append(pg)
        self.y = A4_H - self.mT
        return pg

    def _put(self, text, size=None, bold=False, center=False, para_gap=0.5):
        size = size or self.size
        lh = size * self.line_sp
        ind = 0.0 if (center or bold) else self.indent
        for ln in wrap(text, size, self.width, ind if not center else 0.0):
            while self.y - lh < self.mB:
                self._new_page()
            x = self.mL
            if center:
                w = sum(char_w(c, size) for c in ln)
                x = self.mL + max(0.0, (self.width - w) / 2)
            self._target[-1].text_at(x, self.y - lh, ln, size, bold)
            self.y -= lh
        self.y -= lh * para_gap

    def _emit_pages(self, target, fn):
        self._target = target
        self._new_page()
        fn()

    def layout_chapters(self):
        """排章节正文；返回 {chapter_id: 相对起始页（ch_pages 内 1 起始）}。"""
        rel = {}
        def _run():
            for ch in self.chapters:
                rel[ch["id"]] = len(self._target)
                lvl = ch.get("level", 2)
                hsz = self.size * 1.33 if lvl <= 2 else (self.size * 1.17 if lvl == 3 else self.size * 1.08)
                self._put(f"{ch['number']}　{ch['title']}", size=hsz, bold=True, center=(lvl <= 2), para_gap=0.8)
                for para in ch["paragraphs"]:
                    if para.startswith("#### "):
                        self._put(para[5:], bold=True)
                    elif para.startswith("### "):
                        self._put(para[4:], size=self.size * 1.08, bold=True)
                    elif para.startswith("## "):
                        self._put(para[3:], size=self.size * 1.17, bold=True)
                    elif para.startswith("# "):
                        self._put(para[2:], size=self.size * 1.25, bold=True, center=True)
                    else:
                        self._put(para)
        self._emit_pages(self.ch_pages, _run)
        return rel

    def layout_toc(self, abs_starts):
        """排目录页（两遍法第二遍，页码取 abs_starts）；返回目录页数。"""
        def _run():
            self._put("目　录", size=self.size * 1.33, bold=True, center=True, para_gap=0.8)
            for ch in self.chapters:
                lvl = ch.get("level", 2)
                p = abs_starts.get(ch["id"], 0)
                label = f"{ch['number']}　{ch['title']}"
                pad_n = max(1, 40 - len(label))
                self._put(label + " " * pad_n + str(p), size=self.size * (1.0 if lvl > 2 else 0.92), para_gap=0.15)
        self._emit_pages(self.toc_pages, _run)
        return len(self.toc_pages)

    def compose(self):
        """两遍法收敛。返回 (章绝对起始页 dict, 正文总页数含目录)。"""
        rel = self.layout_chapters()
        K = max(1, self._toc_estimate())
        for _ in range(3):
            self.toc_pages = []
            k = self.layout_toc({cid: K + rel[cid] for cid in rel})
            if k == K:
                break
            K = k
        self.pages = self.toc_pages + self.ch_pages
        return {cid: K + rel[cid] for cid in rel}, len(self.pages)

    def _toc_estimate(self):
        rows = len(self.chapters) + 2
        usable = A4_H - self.mT - self.mB
        per = self.size * self.line_sp * 1.15
        return max(1, math.ceil(rows * per / usable))


def build_pdf(page_streams: list, pn_mode: str = "footer_center", mT: float = 72.0) -> bytes:
    """页面流 → 独立 PDF（经典 xref）；F1 = STSong-Light Type0（非嵌入 CID 中文字体）。

    pn_mode 页码档位（build_style_profile 同枚举）：
      none=不编页码；header_center=页眉居中；footer_center=页脚居中；
      footer_outer=奇数页右/偶数页左（页眉页脚基准 mT/mB 由调用方按样式档传入）。
    """
    n = len(page_streams)
    mB = 28.0
    hdr_y = mT - 14.0 if mT >= 50 else 40.0
    objs = {}          # num -> body bytes
    objs[1] = (b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
               b"/Encoding /UniGB-UCS2-H /DescendantFonts [2 0 R] >>")
    objs[2] = (b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
               b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> "
               b"/DW 1000 /FontDescriptor 3 0 R >>")
    objs[3] = (b"<< /Type /FontDescriptor /FontName /STSong-Light /Flags 4 "
               b"/FontBBox [-25 -254 1000 1000] /ItalicAngle 0 /Ascent 880 "
               b"/Descent -120 /CapHeight 880 /StemV 93 >>")
    pages_root = 4
    first_page = 5
    kids = []
    for i, stream in enumerate(page_streams):
        pn = first_page + i * 2
        cn = pn + 1
        kids.append(f"{pn} 0 R")
        ops = []
        no = str(i + 1)
        if pn_mode == "header_center":
            ops.append(f"BT /F1 9 Tf 0 Tr {(A4_W - 9 * len(no)) / 2:.2f} {A4_H - hdr_y:.2f} Td <{text_hex(no)}> Tj ET")
        elif pn_mode == "footer_outer":
            x = A4_W - 18.0 if (i + 1) % 2 == 1 else 18.0
            ops.append(f"BT /F1 9 Tf 0 Tr {x:.2f} 28 Td <{text_hex(no)}> Tj ET")
        elif pn_mode == "footer_center":
            ops.append(f"BT /F1 9 Tf 0 Tr {(A4_W - 9 * len(no)) / 2:.2f} 28 Td <{text_hex(no)}> Tj ET")
        # pn_mode == "none"：不加页码
        ops.append(stream)
        content = "\n".join(ops).encode("ascii", "ignore")
        objs[pn] = (f"<< /Type /Page /Parent {pages_root} 0 R "
                    f"/MediaBox [0 0 {A4_W:.2f} {A4_H:.2f}] "
                    f"/Resources << /Font << /F1 1 0 R >> >> /Contents {cn} 0 R >>").encode()
        objs[cn] = b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
    catalog = first_page + n * 2
    objs[pages_root] = b"<< /Type /Pages /Kids [" + " ".join(kids).encode() + b"] /Count " + str(n).encode() + b" >>"
    objs[catalog] = b"<< /Type /Catalog /Pages " + str(pages_root).encode() + b" 0 R >>"

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
    xref_off = len(out)
    size = max(objs) + 1
    out += b"xref\n0 " + str(size).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for num in range(1, size):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(size).encode()
            + b" /Root " + str(catalog).encode() + b" 0 R >>\nstartxref\n"
            + str(xref_off).encode() + b"\n%%EOF\n")
    return bytes(out)


# ---- Merger：对象级 PDF 合并（重编号 + Pages 树重建）----

R_RE = re.compile(rb"(\d+)\s+(\d+)\s+R")
PARENT_RE = re.compile(rb"/Parent\s+\d+\s+\d+\s+R\s*")


class Merger:
    """多文档对象级合并：每页 BFS 可达闭包 → 全局重编号 → 重建 Pages 树。

    add() 返回该文档页数；render() 产出合并 PDF 字节（经典 xref，无加密）。
    """

    def __init__(self):
        self.docs = []          # (doc_i, page_nums 按树序)
        self.obj_maps = []      # 每文档 old_num -> new_num
        self.g_objs = {}        # new_num -> body bytes

    def add(self, buf: bytes) -> int:
        d = pdfutil.load_pdf_bytes(buf)
        objects, pages = d["objects"], d["pages"]
        if not pages:
            raise pdfutil.PdfError("文档无页对象")
        keep = {}
        for pn in pages:
            self._bfs(objects, pn, keep)
        mapping = {}
        doc_i = len(self.docs)
        for old in sorted(keep):
            mapping[old] = len(self.g_objs) + 1
            self.g_objs[mapping[old]] = keep[old]
        self.obj_maps.append(mapping)
        self.docs.append((doc_i, pages))
        return len(pages)

    def _bfs(self, objects, root, keep):
        queue = [root]
        while queue:
            n = queue.pop()
            if n in keep or n not in objects:
                continue
            body = objects[n]
            if re.search(rb"/Type\s*/Page(?![s])", body):
                body = PARENT_RE.sub(b"", body)
            refs = [int(m.group(1)) for m in R_RE.finditer(body)]
            keep[n] = body
            for r in refs:
                if r not in keep and r in objects:
                    queue.append(r)

    def _rewrite_refs(self):
        for doc_i, mapping in enumerate(self.obj_maps):
            for new_num, old_num in mapping.items():
                body = self.g_objs[new_num]

                def sub(m):
                    old = int(m.group(1))
                    if old in mapping:
                        return str(mapping[old]).encode() + b" 0 R"
                    return m.group(0)
                self.g_objs[new_num] = R_RE.sub(sub, body)

    def render(self) -> bytes:
        self._rewrite_refs()
        objs = dict(self.g_objs)
        catalog = max(objs) + 1
        pages_root = catalog + 1
        objs[catalog] = b"<< /Type /Catalog /Pages " + str(pages_root).encode() + b" 0 R >>"
        kids, count = [], 0
        for _doc_i, page_nums in self.docs:
            mapping = self.obj_maps[_doc_i]
            for pn in page_nums:
                new_pn = mapping[pn]
                kids.append(f"{new_pn} 0 R")
                body = objs[new_pn]
                if not re.search(rb"/Parent\s+", body):
                    body = body.rstrip()
                    if body.endswith(b">>"):
                        body = body[:-2] + f" /Parent {pages_root} 0 R >>".encode()
                    objs[new_pn] = body
                count += 1
        objs[pages_root] = (b"<< /Type /Pages /Kids [" + " ".join(kids).encode()
                            + b"] /Count " + str(count).encode() + b" >>")
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = {}
        for num in sorted(objs):
            offsets[num] = len(out)
            out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
        xref_off = len(out)
        size = max(objs) + 1
        out += b"xref\n0 " + str(size).encode() + b"\n"
        out += b"0000000000 65535 f \n"
        for num in range(1, size):
            out += f"{offsets[num]:010d} 00000 n \n".encode()
        out += (b"trailer\n<< /Size " + str(size).encode()
                + b" /Root " + str(catalog).encode() + b" 0 R >>\nstartxref\n"
                + str(xref_off).encode() + b"\n%%EOF\n")
        return bytes(out)


# ---- 主流程 ----

def load_chapters(bid: str):
    """按 01c 章节顺序装载 05_chapters/*.md（铁律 2：章序与章名以 01c 为准）。"""
    outline = json.load(open(os.path.join(bid, "01c_format-outline.json"), encoding="utf-8"))
    out = []
    for ch in _common.load_chapters_sorted(bid, outline):
        out.append({
            "id": ch["id"], "number": ch["number"], "title": ch["title"],
            "level": ch.get("level", 2),
            "paragraphs": [p for p in ch["paragraphs"] if p],
        })
    return out


def assemble(bid: str) -> int:
    rc, msgs, meta = _common.gate(bid)
    for m in msgs:
        print(m)
    if rc != 0:
        _common.persist_failed_nodes(bid, meta)
        return rc
    style = _common.read_style_profile(bid)
    if not style:
        print("【执行阻断】07_out/style-profile.yaml 缺失（先运行 build_style_profile.py）")
        return 2
    idx_p = os.path.join(bid, "03b_evidence-index.json")
    if not os.path.exists(idx_p):
        print(f"【执行阻断】{idx_p} 缺失（先运行 index_evidence.py）")
        return 2
    idx = json.load(open(idx_p, encoding="utf-8"))
    by_id = {it["id"]: it for it in idx.get("items", [])}

    chapters = load_chapters(bid)
    if not chapters:
        print("【执行阻断】05_chapters/ 无章节文件")
        return 2

    # 证据页序（按索引 page_count；合并后真值自证）
    seq = [(ev_id, by_id[ev_id]) for ev_id in idx.get("order", []) if ev_id in by_id]

    # [[EV:]] 替换与排版收敛（≤3 轮）：首轮无映射（占位原样排出 body_pages）→
    # 生成 ev_map（证据绝对页码）→ 替换后重排（替换文本长度变化可移页）→ 至 ev_map 稳定。
    # 与目录两遍法同构；3 轮不收敛按末轮页码落盘并在 pagination.json 标注（不阻断）。
    ev_map = {}
    converged = False
    for _round in range(3):
        chapters = load_chapters(bid)
        for ch in chapters:
            ch["paragraphs"] = [_common.replace_ev(p, ev_map) for p in ch["paragraphs"]]
        writer = BodyWriter(style, chapters)
        abs_starts, body_pages = writer.compose()
        new_map = {}
        cursor = body_pages
        for ev_id, it in seq:
            pc = int(it.get("page_count", 1) or 1)
            new_map[ev_id] = (cursor + 1, cursor + pc, str(it.get("attach_no", "")))
            cursor += pc
        if new_map == ev_map:
            converged = True
            break
        ev_map = new_map

    pn_mode = str(style.get("typography", {}).get("page_number", "footer_center"))
    streams = [pg.render() for pg in writer.pages]
    body_pdf = build_pdf(streams, pn_mode=pn_mode, mT=writer.mT)

    merger = Merger()
    n_body = merger.add(body_pdf)
    ev_info = []
    cursor = n_body
    for ev_id, it in seq:
        fp = os.path.join(bid, it["file"])
        if not os.path.exists(fp):
            print(f"【装配错误】证据文件缺失：{it['file']}（{ev_id}）")
            return 1
        try:
            with open(fp, "rb") as f:
                n = merger.add(f.read())
        except pdfutil.PdfError as e:
            print(f"【装配错误】{ev_id} {it['file']}：{e}")
            return 1
        ev_info.append({"id": ev_id, "attach_no": it["attach_no"],
                        "start_page": cursor + 1, "pages": it["page_count"]})
        cursor += n

    final = merger.render()
    out_dir = os.path.join(bid, "07_out")
    os.makedirs(out_dir, exist_ok=True)
    pdf_p = os.path.join(out_dir, "投标文件_含附件.pdf")
    with open(pdf_p, "wb") as f:
        f.write(final)

    # 自证：重读合并结果数页数
    n_final = pdfutil.count_pages(pdf_p)
    total_expected = body_pages + sum(e["pages"] for e in ev_info)
    if n_final != total_expected:
        print(f"【装配错误】页数不自洽：合并后 {n_final} 页 ≠ 正文 {body_pages} + 证据 "
              f"{total_expected - body_pages}（evidence page_count 与实际不符，重跑 index_evidence）")
        return 1

    pagination = {
        "body_pages": body_pages,
        "toc_pages": len(writer.toc_pages),
        "page_number_mode": pn_mode,
        "ev_replaced": len(ev_map),
        "ev_converged": converged,
        "chapters": [{"id": c["id"], "number": c["number"], "title": c["title"],
                      "start_page": abs_starts[c["id"]]} for c in chapters],
        "evidence": ev_info,
        "total_pages": n_final,
        "generated_at": _dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }
    with open(os.path.join(out_dir, "pagination.json"), "w", encoding="utf-8") as f:
        json.dump(pagination, f, ensure_ascii=False, indent=1)

    print(f"合订 PDF 已生成：{pdf_p}")
    print(f"正文 {body_pages} 页（含目录 {len(writer.toc_pages)} 页）＋ 证据 "
          f"{n_final - body_pages} 页 ＝ 共 {n_final} 页")
    if ev_map:
        print(f"[[EV:]] 已替换 {len(ev_map)} 处映射（{'收敛' if converged else '⚠️ 3 轮未收敛，页码取末轮'}）；页码档位 {pn_mode}")
    page_limit = style.get("typography", {}).get("page_limit")
    if page_limit and n_final > int(page_limit):
        print(f"❌ 超出页数上限：{n_final} > {page_limit}（铁律 3；须裁减或澄清）")
        return 1
    if not page_limit:
        print("⚠️ 招标未载明页数上限（铁律 3：按隐含要求人工确认）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    if not os.path.isdir(args.bid):
        print(f"【执行阻断】bid 目录不存在：{args.bid}")
        return 2
    return assemble(args.bid)


if __name__ == "__main__":
    sys.exit(main())
