#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdfutil.py — ④ 共享库：纯标准库 PDF 解析（页计数/对象收集/合并原语）

零三方依赖（套件铁律）。支持：
- 经典 xref 表（PDF ≤1.4 常见）
- xrefstream（PDF 1.5+ 压缩交叉表）＋ objstm 对象流解包（zlib 在标准库）
- 加密 PDF：拒绝并抛 PdfError（提示人工另存为未加密版）
用途：index_evidence.py 页计数 / assemble_pdf.py 合并 / verify 页数复核。
"""
from __future__ import annotations

import re
import zlib


class PdfError(Exception):
    pass


_NUM = rb"\d+"


def _obj_body_at(buf: bytes, offset: int) -> tuple[int, bytes]:
    """从 offset 读 'N G obj ... endobj'，返回 (对象号, 体)。流对象按 endstream 直搜。"""
    m = re.match(rb"(\d+)\s+(\d+)\s+obj", buf[offset:offset + 64])
    if not m:
        raise PdfError(f"对象头解析失败 @offset={offset}")
    start = offset + m.end()
    end = buf.find(b"endobj", start)
    if end < 0:
        raise PdfError(f"对象无 endobj @offset={offset}")
    return int(m.group(1)), buf[start:end]


def _dict_of(body: bytes) -> bytes:
    """取对象体的 <<...>> 首个 dict 部分。"""
    i = body.find(b"<<")
    j = body.rfind(b">>")
    if i < 0 or j < 0 or j < i:
        return b""
    return body[i:j + 2]


def _parse_xref_stream(buf: bytes, offset: int) -> tuple[dict, list]:
    """解析 xrefstream：返回 (trailer, [(type, f1, f2), ...])。"""
    n, body = _obj_body_at(buf, offset)
    d = _dict_of(body)
    wm = re.search(rb"/W\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s*\]", d)
    nm = re.search(rb"/Size\s+(\d+)", d)
    im = re.search(rb"/Index\s*\[(.*?)\]", d, re.S)
    if not (wm and nm):
        raise PdfError("xrefstream 缺 /W 或 /Size")
    w1, w2, w3 = (int(x) for x in wm.groups())
    sm = re.search(rb"stream\r?\n", body)
    if not sm:
        raise PdfError("xrefstream 无 stream")
    raw = body[sm.end():body.rfind(b"endstream")]
    try:
        data = zlib.decompress(raw)
    except zlib.error as e:
        raise PdfError(f"xrefstream 解压失败：{e}")
    if im:
        pairs = [(int(a), int(b)) for a, b in re.findall(rb"(\d+)\s+(\d+)", im.group(1))]
    else:
        pairs = [(0, int(nm.group(1)))]
    wsum = w1 + w2 + w3
    entries = []
    pos = 0
    for start, count in pairs:
        pos = start * wsum
        for _ in range(count):
            chunk = data[pos:pos + wsum]
            if len(chunk) < wsum:
                break
            fs = []
            off = 0
            for w in (w1, w2, w3):
                fs.append(int.from_bytes(chunk[off:off + w], 'big') if w else 0)
                off += w
            entries.append((fs[0] if w1 else 1, fs[1], fs[2]))
            pos += wsum
    trailer = {}
    for k, v in re.findall(rb"/(\w+)\s+(\S+?)(?=/|\s*>>)", d):
        trailer[k.decode()] = v
    return trailer, entries


def _parse_xref_classic(buf: bytes, offset: int) -> tuple[dict, list]:
    """解析经典 xref 表：多个「start count」子段，每段 count 个 20 字节条目。"""
    entries: list[tuple[int, int, int]] = []
    trailer = {}
    pos = offset
    m = re.match(rb"xref\r?\n", buf[pos:pos + 8])
    if not m:
        raise PdfError(f"经典 xref 关键字缺失 @offset={offset}")
    pos += m.end()
    while True:
        hm = re.match(rb"(\d+)\s+(\d+)\r?\n", buf[pos:pos + 32])
        if not hm:
            break
        count = int(hm.group(2))
        pos += hm.end()
        for _ in range(count):
            em = re.match(rb"(\d{10})\s(\d{5})\s([nf])", buf[pos:pos + 20])
            if not em:
                pos += 21
                continue
            entries.append((1 if em.group(3) == b"n" else 0, int(em.group(1)), int(em.group(2))))
            pos += 20
        if buf[pos:pos + 2] == b"\r\n":
            pos += 2
        elif buf[pos:pos + 1] in (b"\n", b"\r"):
            pos += 1
    tm = re.search(rb"trailer\s*<<(.*?)>>", buf[pos:pos + 8192], re.S)
    if tm:
        for k, v in re.findall(rb"/(\w+)\s+([^\s/>]+)", tm.group(1)):
            trailer[k.decode()] = v
    return trailer, entries


def load_pdf_bytes(buf: bytes, path: str = "<bytes>") -> dict:
    """从字节缓冲解析 PDF（与 load_pdf 同口径，供合并原语使用）。"""
    return _parse_buf(buf, path)


def load_pdf(path: str) -> dict:
    with open(path, "rb") as f:
        buf = f.read()
    return _parse_buf(buf, path)


def _parse_buf(buf: bytes, path: str) -> dict:
    if not buf.startswith(b"%PDF"):
        raise PdfError(f"非 PDF 文件（头 %PDF 缺失）：{path}")
    sx = buf.rfind(b"startxref")
    if sx < 0:
        raise PdfError(f"无 startxref：{path}")
    xm = re.search(rb"(\d+)", buf[sx:])
    if not xm:
        raise PdfError(f"startxref 无偏移：{path}")
    xref_off = int(xm.group(1))

    objects: dict[int, bytes] = {}
    pending_objstm: dict[int, int] = {}  # objnum -> (objstm 号, 序)

    if re.match(rb"\d+\s+\d+\s+obj", buf[xref_off:xref_off + 32]):
        trailer, entries = _parse_xref_stream(buf, xref_off)
    else:
        # 经典表；hybrid（/XRefStm）也接住
        trailer, entries = _parse_xref_classic(buf, xref_off)
        hs = re.search(rb"/XRefStm\s+(\d+)", _dump_trailer_bytes(buf, xref_off))
        if hs:
            t2, e2 = _parse_xref_stream(buf, int(hs.group(1)))
            entries = e2 if e2 else entries
            trailer.update({k: v for k, v in t2.items() if k not in trailer})

    if "Encrypt" in trailer or re.search(rb"/Encrypt\s+\d+", _dump_trailer_bytes(buf, xref_off)):
        raise PdfError(f"加密 PDF，不支持解析（请先人工另存为未加密版）：{path}")

    for typ, f1, f2 in entries:
        if typ == 1 and f1 > 0:
            try:
                num, body = _obj_body_at(buf, f1)
                objects[num] = body
            except PdfError:
                pass
        elif typ == 2 and f1 > 0:
            pending_objstm[len(pending_objstm) + 1] = (f1, f2)
    # objstm 解包
    for objstm_num, _idx in {v: None for v in pending_objstm.values()}.keys():
        body = objects.get(objstm_num)
        if body is None:
            try:
                _, body = _obj_body_at(buf, _find_offset_of(buf, objstm_num, entries))
            except PdfError:
                continue
        d = _dict_of(body)
        nm = re.search(rb"/N\s+(\d+)", d)
        fm = re.search(rb"/First\s+(\d+)", d)
        sm = re.search(rb"stream\r?\n", body)
        if not (nm and fm and sm):
            continue
        try:
            data = zlib.decompress(body[sm.end():body.rfind(b"endstream")])
        except zlib.error:
            continue
        n, first = int(nm.group(1)), int(fm.group(1))
        hdr = data[:first].split()
        pairs = [(int(hdr[2 * i]), int(hdr[2 * i + 1])) for i in range(n)]
        for idx in range(len(pairs)):
            objnum, off = pairs[idx]
            start = first + off
            end = (first + pairs[idx + 1][1]) if idx + 1 < len(pairs) else len(data)
            if end > start:
                objects[objnum] = data[start:end].strip(b"\r\n ")
    # Pages 树遍历

    root_ref = trailer.get("Root")
    pages: list[int] = []
    if root_ref is not None:
        rb = root_ref if isinstance(root_ref, bytes) else str(root_ref).encode()
        rm = re.match(rb"(\d+)\s+\d+\s+R", rb)
        if rm:
            root_num = int(rm.group(1))
            cat = objects.get(root_num, b"")
            pm = re.search(rb"/Pages\s+(\d+)\s+\d+\s+R", cat)
            if pm:
                _walk_pages(objects, int(pm.group(1)), pages)
    if not pages:
        # 兜底：正则数 /Type /Page（非 /Pages）
        for num, body in objects.items():
            if re.search(rb"/Type\s*/Page[^s]", body):
                pages.append(num)
        pages.sort()
    return {"objects": objects, "pages": pages, "trailer": trailer, "buf": buf, "path": path}


def _dump_trailer_bytes(buf: bytes, xref_off: int) -> bytes:
    tm = re.search(rb"trailer\s*<<.*?>>", buf[xref_off:xref_off + 8192], re.S)
    return tm.group(0) if tm else b""


def _find_offset_of(buf: bytes, num: int, entries: list) -> int:
    for typ, f1, f2 in entries:
        if typ == 1 and f1 > 0:
            m = re.match(rb"(\d+)\s+\d+\s+obj", buf[f1:f1 + 32])
            if m and int(m.group(1)) == num:
                return f1
    raise PdfError(f"对象 {num} 0 R 偏移未找到")


def _walk_pages(objects: dict, node_num: int, out: list):
    body = objects.get(node_num)
    if body is None:
        return
    if re.search(rb"/Type\s*/Page[^s]", body):
        out.append(node_num)
        return
    km = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
    if not km:
        return
    for ref in re.findall(rb"(\d+)\s+\d+\s+R", km.group(1)):
        _walk_pages(objects, int(ref), out)


def count_pages(path: str) -> int:
    """PDF 页数（完整解析口径：Pages 树遍历；失败抛 PdfError）。"""
    return len(load_pdf(path)["pages"])


if __name__ == "__main__":  # 手测：python pdfutil.py <file.pdf>
    import sys
    print(count_pages(sys.argv[1]))
