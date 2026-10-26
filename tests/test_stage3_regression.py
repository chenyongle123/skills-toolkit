#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage3_regression.py — 阶段 3（④ bid-docx-export v0.2.0 排版导出）永久回归

覆盖：
  T3-1 入口闸门：stage≠recheck_confirmed／缺 form-check／空项／缺 01c → rc=2 零产物；
     ②-A expired 未解决 → 阻断（expiring_soon 不阻断：联动不重判的关键区别）；
     style_source 不一致 → rc=2 且 failed_nodes 落盘 style_source_mismatch；
  T3-2 build_style_profile 基线档：基线值逐项／sources 全 baseline／说明含
     「无招标要求，采用基线」／缺 01c → rc=2；
  T3-3 招标明示档：小四→12pt、页边距解析、逐项来源；空项回落 baseline 并记来源；
  T3-4 甲方模板档：缺 --template → rc=2；合成模板 docx 逐项解析（字体/字号/
     行距/缩进/页边距）；
  T3-5 index_evidence：页数/附件号/id/order、fact_ref 匹配与未匹配告警、
     图片按 1 页计且自动补号、evidence/ 缺失或空 → rc=2；
  T3-6 check_evidence：缺件检出（废标级排前）、索引自洽（page_count 不一致/
     文件缺失）、缺 03b → rc=2；干净索引 → rc=0；
  T3-7 assemble_pdf：页数闭合 total=正文+证据、证据起始页连续、PDF 实测页数
     （pdfutil.count_pages）、page_limit 超限 → rc=1、缺 style-profile → rc=2；
  T3-8 export_docx：章名逐字按 01c 顺序、[[EV:]]→见附件A-01（第3–5页）、
     [[F:]] 剔除、creator 空、页脚 PAGE 域、缺 pagination → rc=2；
  T3-9 scrub_metadata：注入 creator/lastModifiedBy/Company/Template → 全清；
     修订记录存在 → rc=1 不自动接受；暗标标识命中 → rc=1；
  T3-10 verify_docx：残留检出 rc=1 且 stage 不改；干净 → rc=0＋stage=exported＋
     skill_versions 登记；占位符残留检出；暗标命中 rc=1；页数闭合破坏检出；
  T3-11 ④ v0.2.0 交付物在位：SKILL/README 版本、scripts 9 件、references 新件、
     assets schema×2 与基线/叠加 yaml。

用法：python tests/test_stage3_regression.py（退出码 0=全过，1=有失败）
依赖：零三方依赖（PDF 造件为手写经典 xref）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S4 = ROOT / "skills" / "bid-docx-export"
SCRIPTS = S4 / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _common  # noqa: E402
import pdfutil  # noqa: E402

results = []
TMP_BIDS = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("　— " + detail) if detail and not ok else ""))


def run_bid(script, bid, *extra):
    env = dict(os.environ, PYTHONUTF8="1")
    return subprocess.run([sys.executable, str(SCRIPTS / script), "--bid", str(bid), *extra],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


def make_pdf(pages: int) -> bytes:
    """手写经典 xref 的 N 页空白 PDF（零依赖造件）。"""
    kids = b" ".join(b"%d 0 R" % (3 + i) for i in range(pages))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % pages]
    for _ in range(pages):
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> >>")
    out = bytearray(b"%PDF-1.4\n")
    offs = [0]
    for i, bd in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + bd + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for i in range(1, len(objs) + 1):
        out += b"%010d 00000 n \n" % offs[i]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return bytes(out)


# ---------- 合成 bid 工具（全合成，不入真件） ----------

TITLE1 = "施工组织设计"
TITLE2 = "安全管理体系"
BLIND_NAME = "某某建设工程有限公司"


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def wj(path, obj):
    w(path, json.dumps(obj, ensure_ascii=False, indent=1))


def mkbid(typography=None, cards=None, stage="recheck_confirmed", extra_meta=None):
    bid = Path(tempfile.mkdtemp(prefix="t3reg_"))
    TMP_BIDS.append(bid)
    meta = {"schema_version": "0.1", "stage": stage,
            "project": {"name": "测试项目", "no": "N1", "purchaser": "测试业主"},
            "bid_mode": "normal", "style_source": "baseline",
            "deadline": "2027-01-01T10:00+08:00"}
    if extra_meta:
        meta.update(extra_meta)
    wj(bid / "00_metadata.json", meta)
    typo = dict(typography or {"source": "baseline"})
    wj(bid / "01c_format-outline.json", {
        "schema_version": "0.2", "typography": typo,
        "chapters": [{"id": "n-1101", "number": "1", "title": TITLE1, "level": 2},
                     {"id": "n-1102", "number": "2", "title": TITLE2, "level": 2}]})
    body1 = ("本方案依托自有搅拌站与专项设备组织施工，全场推行网格化管理。\n\n"
             "人员与设备投入计划详见后续表格，资质证明见 [[EV:ev-001]]。")
    body2 = ("建立以项目经理为首的安全管理体系[[F:02_facts/qual-001]]，落实逐级交底。\n\n"
             "安全费用专款专用，专项方案经论证后实施。")
    for cid, num, title, body in (("n-1101", "1", TITLE1, body1), ("n-1102", "2", TITLE2, body2)):
        w(bid / "05_chapters" / ("%s.md" % cid),
          "---\nchapter_id: %s\nnumber: \"%s\"\ntitle: %s\nstatus: final\n"
          "word_target: 100\ng4:\n  confirmed: true\n---\n\n%s\n" % (cid, num, title, body))
    w(bid / "06_compliance" / "form-check.md",
      "- 装订方式(binding)：✅ A4胶装\n- 签章(seal)：✅ 电子CA\n"
      "- 页数(page)：✅ 未载明\n- 逐项一致性：✅ 已确认\n")
    items = [{"id": "t-0001", "source_type": "qualification", "source_ref": "c-0008",
              "chapter_id": "n-1101", "response_form": "scan",
              "notes": "施工总承包壹级资质证书"}]
    items.extend(cards or [])
    wj(bid / "03_bid-plan.json", {"schema_version": "0.2", "items": items})
    ev = bid / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "A-01_施工总承包壹级_2027-06.pdf").write_bytes(make_pdf(3))
    (ev / "A-02_审计报告_2022.pdf").write_bytes(make_pdf(2))
    return bid


ORDER = ["build_style_profile.py", "index_evidence.py", "check_evidence.py",
         "assemble_pdf.py", "export_docx.py"]


def chain(bid, last="export_docx.py"):
    for s in ORDER:
        r = run_bid(s, bid)
        if s == last:
            return r
    raise SystemExit("chain: unknown last %s" % last)


def docx_part(bid, part):
    with zipfile.ZipFile(bid / "07_out" / "投标文件.docx") as z:
        return z.read(part).decode("utf-8")


def set_docx_part(bid, part, text):
    p = bid / "07_out" / "投标文件.docx"
    with zipfile.ZipFile(p) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts[part] = text.encode("utf-8")
    fd, tmp = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in parts.items():
            z.writestr(n, d)
    shutil.move(tmp, str(p))


def read_meta(bid):
    return json.loads((bid / "00_metadata.json").read_text(encoding="utf-8"))


# ---------- T3-1 入口闸门 ----------

def t3_1():
    b = mkbid(stage="writing")
    r = run_bid("export_docx.py", b)
    check("T3-1a stage=writing 拒绝导出 rc=2", r.returncode == 2 and "recheck_confirmed" in r.stdout,
          "rc=%s %s" % (r.returncode, r.stdout[-160:]))
    check("T3-1a 零产物", not (b / "07_out" / "投标文件.docx").exists())
    b = mkbid()
    (b / "06_compliance" / "form-check.md").unlink()
    r = run_bid("export_docx.py", b)
    check("T3-1b 缺 form-check.md rc=2", r.returncode == 2 and "form-check" in r.stdout)
    b = mkbid()
    w(b / "06_compliance" / "form-check.md", "- 装订方式：✅ —\n- 签章：✅ 电子CA\n")
    r = run_bid("export_docx.py", b)
    check("T3-1c form-check 空项 rc=2", r.returncode == 2 and "空项" in r.stdout)
    b = mkbid()
    (b / "01c_format-outline.json").unlink()
    r = run_bid("export_docx.py", b)
    check("T3-1d 缺 01c rc=2", r.returncode == 2 and "01c" in r.stdout)
    b = mkbid()
    wj(b / "06_compliance" / "compliance-report.json",
       {"f_qual_timing": [{"id": "f-1", "name": "安全生产许可证", "status": "expired"}]})
    r = run_bid("export_docx.py", b)
    check("T3-1e expired 未解决阻断 rc=2", r.returncode == 2 and "expired" in r.stdout)
    wj(b / "06_compliance" / "compliance-report.json",
       {"f_qual_timing": [{"id": "f-1", "name": "安全生产许可证", "status": "expiring_soon"}]})
    r = run_bid("export_docx.py", b)
    check("T3-1e expiring_soon 不阻断（过闸）", "expired" not in r.stdout and r.returncode == 2
          and "pagination" in r.stdout)
    b = mkbid(extra_meta={"style_source": "tender_required"})
    r = run_bid("export_docx.py", b)
    meta = read_meta(b)
    check("T3-1f style_source 不一致 rc=2 且 failed_nodes 落盘",
          r.returncode == 2 and "style_source" in r.stdout
          and "style_source_mismatch" in meta.get("failed_nodes", []))


# ---------- T3-2/T3-3 build_style_profile ----------

def t3_2():
    b = mkbid()
    r = run_bid("build_style_profile.py", b)
    ok = r.returncode == 0 and (b / "07_out" / "style-profile.yaml").exists() \
        and (b / "07_out" / "排版依据说明.md").exists()
    check("T3-2a 基线档 rc=0 双产物", ok, r.stdout[-160:])
    prof = _common.read_style_profile(str(b))
    t = prof.get("typography", {})
    check("T3-2b 基线值逐项", prof.get("tier") == "baseline" and t.get("font_body") == "仿宋_GB2312"
          and t.get("size_body_pt") == 12 and t.get("line_spacing") == 1.5
          and t.get("first_line_indent_chars") == 2 and t.get("page_number") == "footer_center")
    check("T3-2b sources 全 baseline", set(prof.get("sources", {}).values()) == {"baseline"})
    md = (b / "07_out" / "排版依据说明.md").read_text(encoding="utf-8")
    check("T3-2c 说明含「无招标要求，采用基线」", "无招标要求，采用基线" in md)
    b = mkbid()
    (b / "01c_format-outline.json").unlink()
    r = run_bid("build_style_profile.py", b)
    check("T3-2d 缺 01c rc=2 零产物", r.returncode == 2
          and not (b / "07_out" / "style-profile.yaml").exists())


def t3_3():
    typo = {"source": "tender_required", "font_body": "宋体", "size_body": "小四",
            "line_spacing": "1.5倍", "indent": "首行缩进2字符",
            "margins": "上2.5下2.5左3右3", "page_number": "页脚居中"}
    b = mkbid(typography=typo, extra_meta={"style_source": "tender_required"})
    r = run_bid("build_style_profile.py", b)
    prof = _common.read_style_profile(str(b))
    t, s = prof.get("typography", {}), prof.get("sources", {})
    mg = t.get("margins_cm", {})
    check("T3-3a 招标档逐项采用", r.returncode == 0 and prof.get("tier") == "tender_required"
          and t.get("font_body") == "宋体" and t.get("size_body_pt") == 12
          and t.get("line_spacing") == 1.5 and t.get("first_line_indent_chars") == 2
          and mg.get("top") == 2.5 and mg.get("right") == 3
          and s.get("font_body") == "tender" and s.get("size_body_pt") == "tender")
    typo2 = {"source": "tender_required", "size_body": "小四", "margins": ""}
    b = mkbid(typography=typo2, extra_meta={"style_source": "tender_required"})
    run_bid("build_style_profile.py", b)
    s2 = _common.read_style_profile(str(b)).get("sources", {})
    check("T3-3b 空项回落基线并记来源", s2.get("margins_cm") == "baseline"
          and s2.get("font_body") == "baseline" and s2.get("size_body_pt") == "tender")


# ---------- T3-4 甲方模板档 ----------

TPL_STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:docDefaults><w:pPrDefault><w:pPr>'
              '<w:spacing w:before="0" w:line="360" w:lineRule="auto"/>'
              '<w:ind w:firstLineChars="200" w:firstLine="480"/></w:pPr></w:pPrDefault>'
              '<w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="楷体"/>'
              '<w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>')
TPL_DOC = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:sectPr>'
           '<w:pgMar w:top="1440" w:right="1797" w:bottom="1440" w:left="1797"/>'
           '</w:sectPr></w:body></w:document>')


def t3_4():
    b = mkbid(typography={"source": "client_template"}, extra_meta={"style_source": "client_template"})
    r = run_bid("build_style_profile.py", b)
    check("T3-4a 缺 --template rc=2", r.returncode == 2 and "template" in r.stdout)
    tpl = b / "甲方模板.docx"
    with zipfile.ZipFile(tpl, "w") as z:
        z.writestr("word/styles.xml", TPL_STYLES)
        z.writestr("word/document.xml", TPL_DOC)
    r = run_bid("build_style_profile.py", b, "--template", str(tpl))
    prof = _common.read_style_profile(str(b))
    t, s = prof.get("typography", {}), prof.get("sources", {})
    mg = t.get("margins_cm", {})
    check("T3-4b 模板逐项解析", r.returncode == 0 and prof.get("tier") == "client_template"
          and t.get("font_body") == "楷体" and t.get("size_body_pt") == 14
          and t.get("line_spacing") == 1.5 and t.get("first_line_indent_chars") == 2
          and mg.get("top") == 2.54 and mg.get("left") == 3.17
          and s.get("font_body") == "template", r.stdout[-160:])
    md = (b / "07_out" / "排版依据说明.md").read_text(encoding="utf-8")
    check("T3-4c 说明写明模板档", "甲方模板档" in md)


# ---------- T3-5 index_evidence ----------

def t3_5():
    b = mkbid()
    r = run_bid("index_evidence.py", b)
    check("T3-5a 索引 rc=0", r.returncode == 0 and (b / "03b_evidence-index.json").exists())
    idx = json.loads((b / "03b_evidence-index.json").read_text(encoding="utf-8"))
    its = idx["items"]
    check("T3-5b 条目/页数/附件号/order", len(its) == 2
          and its[0]["attach_no"] == "A-01" and its[0]["page_count"] == 3
          and its[0]["pages"] == "1-3" and its[1]["attach_no"] == "A-02"
          and its[1]["page_count"] == 2 and idx["stats"]["pages_total"] == 5
          and idx["order"] == ["ev-001", "ev-002"])
    check("T3-5c fact_ref 匹配与未匹配", its[0]["fact_ref"] == "c-0008"
          and its[1]["fact_ref"] == "" and "须人工挂接" in its[1]["note"])
    (b / "evidence" / "营业执照.png").write_bytes(b"\x89PNG-not-a-real-image")
    run_bid("index_evidence.py", b)
    idx = json.loads((b / "03b_evidence-index.json").read_text(encoding="utf-8"))
    png = [i for i in idx["items"] if i["file"].endswith(".png")]
    check("T3-5d 图片按 1 页计且自动补号", len(png) == 1 and png[0]["page_count"] == 1
          and png[0]["attach_no"] == "A-03" and "1 页计" in png[0]["note"])
    b2 = mkbid()
    shutil.rmtree(b2 / "evidence")
    r = run_bid("index_evidence.py", b2)
    check("T3-5e evidence/ 缺失 rc=2", r.returncode == 2)
    b2 = mkbid()
    for f in (b2 / "evidence").iterdir():
        f.unlink()
    r = run_bid("index_evidence.py", b2)
    check("T3-5f 空目录 rc=2", r.returncode == 2)


# ---------- T3-6 check_evidence ----------

def t3_6():
    b = mkbid()
    chain(b, last="index_evidence.py")
    r = run_bid("check_evidence.py", b)
    check("T3-6a 干净索引 rc=0", r.returncode == 0
          and (b / "06_compliance" / "evidence-check.md").exists(), r.stdout[-160:])
    cards = [{"id": "t-0002", "source_type": "scoring", "source_ref": "c-9999",
              "chapter_id": "n-1101", "response_form": "scan", "notes": "第三方检测报告"},
             {"id": "t-0000", "source_type": "qualification", "source_ref": "c-7777",
              "chapter_id": "n-1102", "response_form": "scan", "notes": "安全生产许可证"}]
    b = mkbid(cards=cards)
    chain(b, last="index_evidence.py")
    r = run_bid("check_evidence.py", b)
    md = (b / "06_compliance" / "evidence-check.md").read_text(encoding="utf-8")
    ok = (r.returncode == 1 and "缺件[废标级] t-0000" in md and "缺件[一般] t-0002" in md
          and md.index("缺件[废标级]") < md.index("缺件[一般]"))
    check("T3-6b 缺件检出且废标级排前", ok, md[:200])
    b = mkbid()
    chain(b, last="index_evidence.py")
    p = b / "03b_evidence-index.json"
    idx = json.loads(p.read_text(encoding="utf-8"))
    idx["items"][1]["page_count"] = 9
    idx["items"][0]["file"] = "evidence/不存在.pdf"
    p.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    r = run_bid("check_evidence.py", b)
    md = (b / "06_compliance" / "evidence-check.md").read_text(encoding="utf-8")
    check("T3-6c 索引自洽（页数/文件）", r.returncode == 1
          and "page_count=9" in md and "文件缺失" in md)
    b2 = mkbid()
    r = run_bid("check_evidence.py", b2)
    check("T3-6d 缺 03b rc=2", r.returncode == 2)


# ---------- T3-7 assemble_pdf ----------

def t3_7():
    b = mkbid()
    chain(b, last="check_evidence.py")
    r = run_bid("assemble_pdf.py", b)
    ok = r.returncode == 0 and (b / "07_out" / "投标文件_含附件.pdf").exists()
    check("T3-7a 装配 rc=0", ok, r.stdout[-200:])
    pag = json.loads((b / "07_out" / "pagination.json").read_text(encoding="utf-8"))
    ev = pag["evidence"]
    check("T3-7b 页数闭合 total=正文+证据",
          pag["body_pages"] + sum(e["pages"] for e in ev) == pag["total_pages"])
    check("T3-7c 证据起始页连续", ev[0]["start_page"] == pag["body_pages"] + 1
          and ev[1]["start_page"] == ev[0]["start_page"] + ev[0]["pages"]
          and pag["chapters"][0]["start_page"] <= pag["chapters"][1]["start_page"])
    n = pdfutil.count_pages(str(b / "07_out" / "投标文件_含附件.pdf"))
    check("T3-7d PDF 实测页数一致", n == pag["total_pages"], "%s vs %s" % (n, pag["total_pages"]))
    b = mkbid(typography={"source": "baseline", "page_limit": 4})
    run_bid("build_style_profile.py", b)
    run_bid("index_evidence.py", b)
    r = run_bid("assemble_pdf.py", b)
    check("T3-7e page_limit 超限 rc=1", r.returncode == 1 and "超出页数上限" in r.stdout)
    b = mkbid()
    run_bid("index_evidence.py", b)
    r = run_bid("assemble_pdf.py", b)
    check("T3-7f 缺 style-profile rc=2", r.returncode == 2 and "style-profile" in r.stdout)


# ---------- T3-8 export_docx ----------

def t3_8():
    b = mkbid()
    r = chain(b)
    dx = b / "07_out" / "投标文件.docx"
    with zipfile.ZipFile(dx) as z:
        parts = set(z.namelist())
        doc = z.read("word/document.xml").decode("utf-8")
        core = z.read("docProps/core.xml").decode("utf-8")
        footer = z.read("word/footer1.xml").decode("utf-8")
    txt = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", doc))
    check("T3-8a docx 生成与部件", r.returncode == 0 and dx.exists()
          and {"word/document.xml", "word/styles.xml", "word/footer1.xml", "docProps/core.xml"} <= parts)
    check("T3-8b 章名逐字按 01c 顺序", TITLE1 in txt and TITLE2 in txt
          and txt.index(TITLE1) < txt.index(TITLE2))
    check("T3-8c [[EV:]] 替换", "见附件A-01（第3\u20135页）" in txt and "[[EV:" not in txt)
    check("T3-8d [[F:]] 剔除且正文保留", "[[F:" not in txt and "[[S:" not in txt
          and "逐级交底" in txt)
    check("T3-8e creator 空与 PAGE 域",
          "<dc:creator></dc:creator>" in core and "PAGE" in footer)
    b = mkbid()
    chain(b, last="assemble_pdf.py")
    (b / "07_out" / "pagination.json").unlink()
    r = run_bid("export_docx.py", b)
    check("T3-8f 缺 pagination rc=2", r.returncode == 2 and "pagination" in r.stdout)


# ---------- T3-9 scrub_metadata ----------

def _inject_dirty(b):
    core = docx_part(b, "docProps/core.xml")
    core = core.replace("<dc:creator></dc:creator>", "<dc:creator>张三</dc:creator>")
    core = core.replace("<dc:creator/>", "<dc:creator>张三</dc:creator>")
    core = core.replace("<cp:lastModifiedBy></cp:lastModifiedBy>", "<cp:lastModifiedBy>李四</cp:lastModifiedBy>")
    core = core.replace("<cp:lastModifiedBy/>", "<cp:lastModifiedBy>李四</cp:lastModifiedBy>")
    set_docx_part(b, "docProps/core.xml", core)
    app = docx_part(b, "docProps/app.xml")
    app = app.replace("</Properties>",
                      "<Company>%s</Company><Template>C:\\Users\\tester\\AppData\\t.docx</Template>"
                      "</Properties>" % BLIND_NAME)
    set_docx_part(b, "docProps/app.xml", app)


def t3_9():
    b = mkbid()
    chain(b)
    _inject_dirty(b)
    r = run_bid("scrub_metadata.py", b, "--mode", "normal")
    core2, app2 = docx_part(b, "docProps/core.xml"), docx_part(b, "docProps/app.xml")
    check("T3-9a 普通标清四字段 rc=0", r.returncode == 0 and "张三" not in core2
          and "李四" not in core2 and "<Company>" not in app2 and "<Template>" not in app2)
    doc = docx_part(b, "word/document.xml")
    set_docx_part(b, "word/document.xml",
                  doc.replace("</w:body>", '<w:ins w:id="1"><w:r><w:t>x</w:t></w:r></w:ins></w:body>'))
    r = run_bid("scrub_metadata.py", b, "--mode", "normal")
    check("T3-9b 修订记录不自动接受 rc=1", r.returncode == 1 and "修订记录" in r.stdout)
    b = mkbid(extra_meta={"bid_mode": "blind"})
    chain(b)
    doc = docx_part(b, "word/document.xml")
    set_docx_part(b, "word/document.xml",
                  doc.replace("网格化管理", "网格化管理（%s）" % BLIND_NAME, 1))
    r = run_bid("scrub_metadata.py", b, "--identity", "%s,王五" % BLIND_NAME)
    check("T3-9c 暗标标识命中 rc=1", r.returncode == 1 and "暗标标识命中" in r.stdout
          and "正文" in r.stdout)


# ---------- T3-10 verify_docx ----------

def t3_10():
    b = mkbid()
    chain(b)
    _inject_dirty(b)
    r = run_bid("verify_docx.py", b)
    meta = read_meta(b)
    check("T3-10a 残留检出 rc=1 且 stage 不改", r.returncode == 1 and "creator 残留" in r.stdout
          and "Company" in r.stdout and "模板路径" in r.stdout
          and meta["stage"] == "recheck_confirmed")
    b = mkbid()
    chain(b)
    r = run_bid("verify_docx.py", b)
    meta = read_meta(b)
    check("T3-10b 干净通过 rc=0＋stage=exported＋版本登记", r.returncode == 0
          and meta["stage"] == "exported"
          and meta["skill_versions"].get("bid-docx-export") == "0.2.2"
          and "交付完成" in r.stdout, r.stdout[-200:])
    b = mkbid(extra_meta={"bid_mode": "blind"})
    chain(b)
    doc = docx_part(b, "word/document.xml")
    set_docx_part(b, "word/document.xml",
                  doc.replace("网格化管理", "网格化管理（%s）" % BLIND_NAME, 1))
    r = run_bid("verify_docx.py", b, "--identity", BLIND_NAME)
    check("T3-10c 暗标命中 rc=1", r.returncode == 1 and "暗标标识命中[正文]" in r.stdout)
    b = mkbid()
    chain(b)
    ch = b / "05_chapters" / "n-1101.md"
    ch.write_text(ch.read_text(encoding="utf-8")
                  + "\n\n特殊工况下的补充措施【待填：专项参数】。\n", encoding="utf-8")
    run_bid("assemble_pdf.py", b)
    run_bid("export_docx.py", b)
    r = run_bid("verify_docx.py", b)
    check("T3-10d 占位符残留检出", r.returncode == 1 and "【待填" in r.stdout)
    b = mkbid()
    chain(b)
    p = b / "07_out" / "pagination.json"
    pag = json.loads(p.read_text(encoding="utf-8"))
    pag["total_pages"] = 99
    p.write_text(json.dumps(pag, ensure_ascii=False), encoding="utf-8")
    r = run_bid("verify_docx.py", b)
    check("T3-10e 页数闭合破坏检出", r.returncode == 1
          and ("页数闭合" in r.stdout or "实际页数" in r.stdout))
    b = mkbid()
    chain(b)
    doc = docx_part(b, "word/document.xml")
    set_docx_part(b, "word/document.xml",
                  doc.replace("</w:body>", '<w:ins w:id="1"><w:r><w:t>x</w:t></w:r></w:ins></w:body>'))
    r = run_bid("verify_docx.py", b)
    check("T3-10f 修订记录残留检出", r.returncode == 1 and "修订记录残留" in r.stdout)


# ---------- T3-11 交付物在位 ----------

def t3_11():
    skill = (S4 / "SKILL.md").read_text(encoding="utf-8")
    check("T3-11a SKILL v0.2.2", re.search(r"^version:\s*0\.2\.2\s*$", skill, re.M) is not None)
    scripts = sorted(p.name for p in SCRIPTS.glob("*.py"))
    expect = ["_common.py", "assemble_pdf.py", "build_style_profile.py", "check_evidence.py",
              "export_docx.py", "index_evidence.py", "pdfutil.py", "scrub_metadata.py",
              "verify_docx.py"]
    check("T3-11b scripts 9 件", scripts == expect, str(scripts))
    for f in ("references/证明材料装配规则.md", "references/样式与编号规范.md",
              "references/雷同与元数据清理.md", "assets/style-profile.schema.json",
              "assets/evidence-index.schema.json", "assets/metadata.schema.json",
              "assets/style-profiles/通用中文基线.yaml", "assets/style-profiles/暗标叠加层.yaml"):
        check("T3-11c 在位 " + f, (S4 / f).exists())
    check("T3-11d 铁律块在位", "IRONLAWS:BEGIN" in skill and "IRONLAWS:END" in skill)
    readme = (S4 / "README.md").read_text(encoding="utf-8")
    check("T3-11e README 版本行", "0.2.2" in readme)
    # f) F16b：基线单源——BASELINE 从 yaml 加载（非硬编码），值逐键一致
    sys.path.insert(0, str(SCRIPTS))
    import build_style_profile as BSP
    bl = BSP.BASELINE
    check("T3-11f 基线单源（BASELINE 载自 yaml）",
          bl.get("font_body") == "仿宋_GB2312" and bl.get("size_body_pt") == 12.0
          and bl.get("line_spacing") == 1.5 and bl.get("first_line_indent_chars") == 2
          and bl.get("margins_cm") == {"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17}
          and bl.get("page_number") == "footer_center", str(bl))


# ---------- T3-12 闸门负例与新行为（批次1收口回归） ----------

def t3_12():
    # a) C5：②-A expired 联动阻断（f_qual_timing 新契约 dict 形态）
    b = mkbid()
    wj(b / "06_compliance" / "compliance-report.json",
       {"f_qual_timing": {"status": "expired",
                          "items": [{"id": "q-0001", "name": "安全生产许可证",
                                     "state": "expired", "detail": "2023-06-01 已过期"}]}})
    r = run_bid("export_docx.py", b)
    check("T3-12a expired 联动阻断", r.returncode == 2
          and "expired" in r.stdout and "阻断导出" in r.stdout)
    # a2) 旧式 list 形态（读侧兼容）同样阻断
    b = mkbid()
    wj(b / "06_compliance" / "compliance-report.json",
       {"f_qual_timing": [{"id": "q-0002", "state": "expired", "name": "质检报告"}]})
    r = run_bid("export_docx.py", b)
    check("T3-12a2 expired 旧式 list 兼容阻断", r.returncode == 2 and "expired" in r.stdout)
    # b) C6：draft 章节阻断（导出只接受 final）
    b = mkbid()
    ch = b / "05_chapters" / "n-1102.md"
    ch.write_text(ch.read_text(encoding="utf-8").replace("status: final", "status: draft"),
                  encoding="utf-8")
    r = run_bid("export_docx.py", b)
    check("T3-12b draft 章阻断", r.returncode == 2 and "status≠final" in r.stdout)
    # c) C12：01c 有节点而无章节文件（缺章）阻断
    b = mkbid()
    o1c = b / "01c_format-outline.json"
    oc = json.loads(o1c.read_text(encoding="utf-8"))
    oc["chapters"].append({"id": "n-1103", "number": "3", "title": "附表", "level": 2})
    o1c.write_text(json.dumps(oc, ensure_ascii=False), encoding="utf-8")
    r = run_bid("export_docx.py", b)
    check("T3-12c 缺章阻断", r.returncode == 2 and "缺章" in r.stdout and "n-1103" in r.stdout)
    # d) F12：skills-lock 运行时自检——对齐静默 / 漂移警告
    sys.path.insert(0, str(SCRIPTS))
    import _common as C4C
    check("T3-12d lock 对齐静默", C4C.check_skill_lock() == [])
    from unittest import mock
    with mock.patch.object(C4C, "read_skill_version", return_value="9.9.9"):
        warns = C4C.check_skill_lock()
    check("T3-12d2 lock 漂移警告", len(warns) == 1 and "版本不对齐" in warns[0])
    # e) F14：中英文之间误加空格检出（信息态不抬 rc）
    b = mkbid()
    chain(b)
    doc = docx_part(b, "word/document.xml")
    set_docx_part(b, "word/document.xml",
                  doc.replace("网格化管理", "网格化 management 管理", 1))
    r = run_bid("verify_docx.py", b)
    check("T3-12e 中英文加空格检出", r.returncode == 0 and "加空格" in r.stdout)
    # f) F7：装配 PDF 文本层暗标标识扫描（BodyWriter UCS2-BE hex 载体）
    b = mkbid()
    chain(b, last="assemble_pdf.py")
    hits = C4C.pdf_identity_hits(str(b / "07_out" / "投标文件_含附件.pdf"),
                                 [TITLE1, "绝不存在的词组"])
    check("T3-12f PDF 文本层扫描", hits == [TITLE1])
    # g/h) F4：页码档位 none/header_center（docx 部件动态组装）
    b = mkbid(typography={"source": "tender_required", "page_number": "不编页码"})
    r = chain(b)
    with zipfile.ZipFile(b / "07_out" / "投标文件.docx") as z:
        parts = set(z.namelist())
    check("T3-12g 页码档 none 无页码部件", r.returncode == 0
          and "页码档位 none" in r.stdout
          and not any(p.startswith("word/footer") or p.startswith("word/header") for p in parts))
    b = mkbid(typography={"source": "tender_required", "page_number": "页眉居中"})
    r = chain(b)
    with zipfile.ZipFile(b / "07_out" / "投标文件.docx") as z:
        parts = set(z.namelist())
        hdr = z.read("word/header1.xml").decode("utf-8")
    check("T3-12h 页码档 header_center", r.returncode == 0 and "页码档位 header_center" in r.stdout
          and "word/header1.xml" in parts and "word/footer1.xml" not in parts
          and "PAGE" in hdr)
    b = mkbid(typography={"source": "tender_required", "page_number": "页脚外侧（奇偶页）"})
    r = chain(b)
    with zipfile.ZipFile(b / "07_out" / "投标文件.docx") as z:
        parts = set(z.namelist())
        st = z.read("word/settings.xml").decode("utf-8")
    check("T3-12i 页码档 footer_outer", r.returncode == 0
          and "word/footer1.xml" in parts and "word/footer2.xml" in parts
          and "evenAndOddHeaders" in st)
    # j) F5：招标档字体不在白名单 → 照录但警告（不回落不阻断）
    b = mkbid(typography={"source": "tender_required", "font_body": "方正小标宋简体"})
    r = run_bid("build_style_profile.py", b)
    yml = (b / "07_out" / "style-profile.yaml").read_text(encoding="utf-8")
    check("T3-12j 字体白名单外照录＋警告", r.returncode == 0
          and "font_body: 方正小标宋简体" in yml and "不在常用字体白名单" in r.stdout)


def main():
    try:
        for fn in (t3_1, t3_2, t3_3, t3_4, t3_5, t3_6, t3_7, t3_8, t3_9, t3_10, t3_11, t3_12):
            print("\n== %s ==" % fn.__name__)
            fn()
    finally:
        for b in TMP_BIDS:
            shutil.rmtree(b, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    print()
    print("阶段 3 回归（T3-1~T3-12）：共 %d 项，通过 %d，失败 %d"
          % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("\n失败明细：")
        for name, _, detail in failed:
            print("  FAIL %s　— %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
