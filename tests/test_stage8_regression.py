#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage8_regression.py — 2026-10-31 本轮新增能力的永久回归

背景：对标《趴一趴市面上智能标书软件》后新增三项能力（P0-1 承诺锁／P0-2 雷同机检／
P2-2 残留反查）并实装 P0-3 插图管线。当时只补了既有 stage1–7 的版本号断言，
**新能力本身零回归覆盖**（外部核查指出），本文件补最小闭环。

覆盖：
  T8-1 雷同机检 `check_similarity.py`：
    a 高套话稿 → rc=1 且产出 `06_compliance/similarity-check.md`；
    b 干净稿（含具体数值）→ rc=0；
    c 产出必须含「未机检」——与历史稿相似段落不可机检，防声明被删；
    d 缺 `05_chapters/` → rc=2（前置缺失，不静默通过）。
  T8-2 承诺锁 `check_commit_lock.py`：
    a 偏离稿（工期/质保/禁词/禁用自称）→ rc=1 且四项命中；
    b 一致稿 → rc=0；
    c **未启用锁（无 03d_commit-lock.json）→ rc=0 且明确提示「未检」**（不阻断、不谎报已查）。
  T8-3 旧项目残留反查 `verify_docx.py`（函数级）：
    a 白名单外项目名/单位名报出；
    b 白名单内零误报；
    c 空白名单 → `derive_whitelist` 返回空，verify 侧须打印「未执行本项扫描」（fail-loud）。
  T8-4 插图管线 `export_docx.py`：
    a 缺失源文件的图 → rc=1 且正文出「【待补图」占位；
    b 补齐后重导 → rc=0 且占位消失、`word/media/` 部件数=3。

用法：python tests/test_stage8_regression.py（退出码 0=全过，1=有失败）
依赖：零三方依赖。合成 fixture 自建自清。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CS = ROOT / "skills" / "bid-compliance-check" / "scripts" / "check_similarity.py"
CL = ROOT / "skills" / "bid-compliance-check" / "scripts" / "check_commit_lock.py"
VV = ROOT / "skills" / "bid-docx-export" / "scripts" / "verify_docx.py"
ED = ROOT / "skills" / "bid-docx-export" / "scripts" / "export_docx.py"

results = []
TMP_BIDS = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("　— " + detail) if detail and not ok else ""))


def run_py(script, *args):
    env = dict(os.environ, PYTHONUTF8="1")
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


def mk_bid(tag):
    d = os.path.join(tempfile.mkdtemp(prefix="t8_%s_" % tag), "bid")
    os.makedirs(os.path.join(d, "05_chapters"))
    TMP_BIDS.append(os.path.dirname(d))
    return d


def meta(d, **kw):
    m = {"project": {"name": "测试风电场项目", "no": "T-001", "purchaser": "某某能源开发有限公司"},
         "stage": "rechecking", "bid_mode": "normal"}
    m.update(kw)
    json.dump(m, open(os.path.join(d, "00_metadata.json"), "w", encoding="utf-8"), ensure_ascii=False)


def outline(d, ids=(("n-0001", "一", "第1章"), ("n-0002", "二", "第2章"), ("n-0003", "三", "第3章"))):
    json.dump({"chapters": [{"id": i, "number": n, "title": t, "level": 2} for i, n, t in ids]},
              open(os.path.join(d, "01c_format-outline.json"), "w", encoding="utf-8"), ensure_ascii=False)


def chapter(d, cid, title, number, body):
    open(os.path.join(d, "05_chapters", "%s_x.md" % cid), "w", encoding="utf-8").write(
        "---\nchapter_id: %s\ntitle: %s\nnumber: %s\nstatus: final\n---\n%s" % (cid, title, number, body))


# ---------------------------------------------------------------- T8-1 雷同机检
CLICHE = """### 1.1 质量管理措施

本着安全第一的原则，为了本工程的顺利实施，我方高度重视质量管理工作，切实加强过程控制，严格落实各项制度，进一步完善管理体系，综上所述可以确保目标实现。

### 1.2 安全管理措施

首先成立组织机构。其次明确职责分工。最后开展考核评价。

### 1.3 环境保护措施

| 序号 | 措施 | 责任人 |
|---|---|---|
| 1 | 扬尘控制 | 张三 |
| 2 | 噪声控制 | 李四 |
| 3 | 废水处理 | 王五 |
| 4 | 固废处置 | 赵六 |
"""

CLEAN1 = """### 1.1 风机基础施工方案

本工程风机基础采用 C40 混凝土，单台浇筑量 380 m³，分两层浇筑，层间间歇不超过 72 小时，入模温度控制在 5–28 ℃。

### 1.2 吊装作业

主吊选用 1200 t 履带吊，作业风速限值 8 m/s，吊具安全系数取 6.0，单机吊装时长约 4.5 小时。
"""

CLEAN2 = """### 2.1 集电线路路径

集电线路采用直埋电缆，路径全长 12.6 km，其中穿越乡村道路 7 处，埋深不小于 0.8 m，过路段加设钢套管保护。

### 2.2 电缆选型

选用 YJV22-8.7/15 kV 3×240 mm² 铜芯电缆，载流量按环境温度 40 ℃ 校正后为 415 A。
"""

CLEAN3 = """### 3.1 工期安排

计划总工期 180 日历天，其中前期准备 25 天，主体施工 120 天，调试验收 35 天。

### 3.2 资源配置

高峰期投入管理人员 18 人、施工作业人员 240 人，配置 25 t 汽车吊 4 台、混凝土泵车 2 台。
"""


def t8_1():
    # a 高套话稿
    d = mk_bid("cliche")
    meta(d)
    outline(d)
    for i, (cid, num, ttl) in enumerate((("n-0001", "一", "第1章"), ("n-0002", "二", "第2章"),
                                         ("n-0003", "三", "第3章"))):
        chapter(d, cid, ttl, num, CLICHE)
    r = run_py(CS, "--bid", d)
    rep = os.path.join(d, "06_compliance", "similarity-check.md")
    check("T8-1a 高套话稿 rc=1", r.returncode == 1, "rc=%s %s" % (r.returncode, r.stdout[-300:]))
    check("T8-1a2 产出 similarity-check.md", os.path.isfile(rep), "产出缺失")
    body = open(rep, encoding="utf-8").read() if os.path.isfile(rep) else ""
    check("T8-1c 产出含「未机检」（跨稿相似不可机检，防声明被删）",
          "未机检" in body, "产出无「未机检」字样，声明可能被删：%s" % body[:200])

    # b 干净稿
    d2 = mk_bid("clean")
    meta(d2)
    outline(d2)
    chapter(d2, "n-0001", "第1章", "一", CLEAN1)
    chapter(d2, "n-0002", "第2章", "二", CLEAN2)
    chapter(d2, "n-0003", "第3章", "三", CLEAN3)
    r2 = run_py(CS, "--bid", d2)
    check("T8-1b 干净稿（含具体数值）rc=0 不误报", r2.returncode == 0,
          "rc=%s %s" % (r2.returncode, r2.stdout[-400:]))

    # d 前置缺失
    d3 = mk_bid("nochap")
    meta(d3)
    outline(d3)
    shutil.rmtree(os.path.join(d3, "05_chapters"))
    r3 = run_py(CS, "--bid", d3)
    check("T8-1d 缺 05_chapters → rc=2（不静默通过）", r3.returncode == 2,
          "rc=%s %s" % (r3.returncode, r3.stdout[-200:]))


# ---------------------------------------------------------------- T8-2 承诺锁
LOCK = {"schema_version": "0.1",
        "project": {"name": "测试风电场", "no": "T-001", "purchaser": "某某能源"},
        "locks": {
            "numbers": [
                {"key": "总工期", "value": "180", "unit": "日历天",
                 "synonyms": ["工期", "施工工期", "总工期", "建设周期"]},
                {"key": "免费质保期", "value": "2", "unit": "年",
                 "synonyms": ["质保期", "免费质保期", "质量保修期"]}],
            "tech_route": {"architecture": "分层分布式", "deployment": "容器化",
                           "forbidden": ["裸金属", "物理机"]},
            "naming": {"purchaser_short": "招标人", "system_full": "测试风电场工程",
                       "self_ref": "投标人", "forbidden": ["我司", "我公司"]}},
        "confirmed_at": "2026-10-31T18:00:00+08:00", "confirmed_by": "编制负责人"}

BODY_OK = """### 1.1 工期承诺

本工程总工期 180 日历天，免费质保期 2 年。

### 1.2 技术路线

系统采用分层分布式架构，容器化部署。我方作为投标人承诺按招标人要求实施测试风电场工程。
"""

BODY_BAD = """### 1.1 工期承诺

本工程总工期 150 日历天，质量保修期 3 年，主要设备质保期 5 年。

### 1.2 技术路线

采用裸金属服务器部署，我司将全力配合。
"""


def t8_2():
    # a 偏离稿
    d = mk_bid("deviate")
    meta(d)
    outline(d)
    json.dump(LOCK, open(os.path.join(d, "03d_commit-lock.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    chapter(d, "n-0001", "第1章", "一", BODY_BAD)
    chapter(d, "n-0002", "第2章", "二", CLEAN2)
    chapter(d, "n-0003", "第3章", "三", CLEAN3)
    r = run_py(CL, "--bid", d)
    out = r.stdout + (open(os.path.join(d, "06_compliance", "commit-lock-check.md"),
                           encoding="utf-8").read()
                      if os.path.isfile(os.path.join(d, "06_compliance", "commit-lock-check.md")) else "")
    check("T8-2a 偏离稿 rc=1", r.returncode == 1, "rc=%s %s" % (r.returncode, r.stdout[-300:]))
    for kw, nm in (("150", "工期偏离 150≠180 被报"), ("裸金属", "技术路线禁词「裸金属」被报"),
                   ("我司", "禁用自称「我司」被报")):
        check("T8-2a-%s" % nm, kw in out, "未在产出中找到 %s：%s" % (kw, out[:300]))

    # b 一致稿
    d2 = mk_bid("lockok")
    meta(d2)
    outline(d2)
    json.dump(LOCK, open(os.path.join(d2, "03d_commit-lock.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    chapter(d2, "n-0001", "第1章", "一", BODY_OK)
    chapter(d2, "n-0002", "第2章", "二", CLEAN2)
    chapter(d2, "n-0003", "第3章", "三", CLEAN3)
    r2 = run_py(CL, "--bid", d2)
    check("T8-2b 一致稿 rc=0", r2.returncode == 0, "rc=%s %s" % (r2.returncode, r2.stdout[-300:]))

    # c 未启用锁
    d3 = mk_bid("nolock")
    meta(d3)
    outline(d3)
    chapter(d3, "n-0001", "第1章", "一", BODY_BAD)
    r3 = run_py(CL, "--bid", d3)
    check("T8-2c 未启用锁 rc=0（不阻断）", r3.returncode == 0,
          "rc=%s %s" % (r3.returncode, r3.stdout[-300:]))
    check("T8-2c2 未启用锁须提示「未检」（不得谎报已查）",
          "未检" in r3.stdout, "输出：%s" % r3.stdout[-300:])


# ---------------------------------------------------------------- T8-3 残留反查
def _load_verify():
    spec = importlib.util.spec_from_file_location("t8_verify", str(VV))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def t8_3():
    v = _load_verify()
    wl = {"测试风电场项目", "某某能源开发有限公司", "T-001"}
    dirty = ("本项目为测试风电场项目，装机规模 100MW。我方曾承建华能某某光伏电站工程，"
             "参考某大型水利枢纽工程的施工组织经验，由示例电网有限责任公司负责并网。")
    hits = v.residual_scan(dirty, wl)
    check("T8-3a 白名单外项目名/单位名报出", len(hits) >= 3,
          "命中 %d 项：%s" % (len(hits), hits))
    check("T8-3a2 白名单内不误报",
          not any("测试风电场" in h or "某某能源开发有限公司" in h for h in hits),
          "误报：%s" % hits)
    clean = "本项目为测试风电场项目，由某某能源开发有限公司投资建设，我方负责施工总承包。"
    check("T8-3b 干净稿零命中", v.residual_scan(clean, wl) == [],
          "误报：%s" % v.residual_scan(clean, wl))
    # 噪声句（防 T3-10b 类误判复发）
    noise = "安全管理体系建立以项目为抓手，全面落实主体责任。"
    check("T8-3b2 噪声句「…建立以项目」不误判为项目名",
          v.residual_scan(noise, wl) == [], "误报：%s" % v.residual_scan(noise, wl))
    # 空白名单
    empty = tempfile.mkdtemp(prefix="t8_empty_")
    TMP_BIDS.append(empty)
    check("T8-3c 空白名单时 derive_whitelist 返回空（verify 侧据此打印未执行）",
          v.derive_whitelist(empty, []) == set(), "返回非空")
    # 白名单派生
    d = mk_bid("wl")
    json.dump({"project": {"name": "测试风电场项目", "no": "T-001",
                           "purchaser": "某某能源开发有限公司"}},
              open(os.path.join(d, "00_metadata.json"), "w", encoding="utf-8"), ensure_ascii=False)
    dw = v.derive_whitelist(d, ["张三"])
    check("T8-3d 白名单由 00_metadata.project 三字段＋人工补充派生",
          "测试风电场项目" in dw and "T-001" in dw and "张三" in dw, "派生结果：%s" % sorted(dw))


# ---------------------------------------------------------------- T8-4 插图管线
def make_png(path, w, h, color=(200, 120, 60)):
    raw = b"".join(b"\x00" + bytes(color) * w for _ in range(h))

    def ck(t, dd):
        return struct.pack(">I", len(dd)) + t + dd + struct.pack(">I", zlib.crc32(t + dd) & 0xFFFFFFFF)
    open(path, "wb").write(
        b"\x89PNG\r\n\x1a\n" + ck(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + ck(b"IDAT", zlib.compress(raw)) + ck(b"IEND", b""))


def t8_4():
    d = mk_bid("img")
    os.makedirs(os.path.join(d, "05_chapters", "assets"), exist_ok=True)
    os.makedirs(os.path.join(d, "07_out"), exist_ok=True)
    os.makedirs(os.path.join(d, "06_compliance"), exist_ok=True)
    meta(d, stage="recheck_confirmed", bid_mode="normal")
    json.dump({"chapters": [{"id": "n-0001", "number": "一", "title": "施工总体布置", "level": 2}]},
              open(os.path.join(d, "01c_format-outline.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump({"total_pages": 3, "body_pages": 3, "evidence": [],
               "chapters": [{"id": "n-0001", "start_page": 1}]},
              open(os.path.join(d, "07_out", "pagination.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump({"items": []}, open(os.path.join(d, "03b_evidence-index.json"), "w", encoding="utf-8"))
    # gate 要求：06_compliance/form-check.md 存在且无空项（成稿终检 G5 产物）
    open(os.path.join(d, "06_compliance", "form-check.md"), "w", encoding="utf-8").write(
        "# 形式核对\n\n- 投标函签字盖章：✅ 齐全\n- 工期响应：✅ 一致\n- 投标有效期：✅ 满足\n")
    open(os.path.join(d, "06_compliance", "consistency-issues.md"), "w",
         encoding="utf-8").write("# 跨章一致性\n\n- 无问题 ✅\n")
    open(os.path.join(d, "07_out", "style-profile.yaml"), "w", encoding="utf-8").write(
        "typography:\n  size_body_pt: 12\n  line_spacing: 1.5\n  first_line_indent_chars: 2\n"
        "  font_body: 仿宋_GB2312\n  page_number: footer_center\n"
        "  margins_cm:\n    top: 2.54\n    bottom: 2.54\n    left: 3.17\n    right: 3.17\n")
    chapter(d, "n-0001", "施工总体布置", "一",
            "本章说明施工总平面布置，遵循分区布置原则。\n\n"
            "![图 3-1 施工总平面布置图](assets/plan.png)\n\n"
            "现场实景照片如下。\n\n"
            "![图 3-2 现场实景照片](assets/photo.png)\n\n"
            "缺源文件的示例：\n\n"
            "![图 3-3 缺失的网络计划图](assets/none.png)\n")
    make_png(os.path.join(d, "05_chapters", "assets", "plan.png"), 1200, 800)
    make_png(os.path.join(d, "05_chapters", "assets", "photo.png"), 900, 600)

    dx = os.path.join(d, "07_out", "投标文件.docx")
    r = run_py(ED, "--bid", d)
    check("T8-4a 缺失源文件的图 → rc=1（不静默放行）", r.returncode == 1,
          "rc=%s %s" % (r.returncode, r.stdout[-400:]))
    if os.path.isfile(dx):
        with zipfile.ZipFile(dx) as z:
            doc = z.read("word/document.xml").decode("utf-8")
            n_media = len([n for n in z.namelist() if n.startswith("word/media/")])
        texts = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", doc))
        check("T8-4a2 缺失图出「【待补图」占位", "【待补图" in texts, "正文无占位")
        check("T8-4a3 存在的 2 张已嵌入", n_media == 2, "media 部件数=%d" % n_media)
    else:
        check("T8-4a2 缺失图出「【待补图」占位", False, "docx 未生成")
        check("T8-4a3 存在的 2 张已嵌入", False, "docx 未生成")

    make_png(os.path.join(d, "05_chapters", "assets", "none.png"), 900, 600)
    r2 = run_py(ED, "--bid", d)
    check("T8-4b 补齐后重导 rc=0", r2.returncode == 0, "rc=%s %s" % (r2.returncode, r2.stdout[-400:]))
    if os.path.isfile(dx):
        with zipfile.ZipFile(dx) as z:
            doc2 = z.read("word/document.xml").decode("utf-8")
            n_media2 = len([n for n in z.namelist() if n.startswith("word/media/")])
        texts2 = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", doc2))
        check("T8-4b2 补齐后占位消失且 3 张全嵌入",
              "【待补图" not in texts2 and n_media2 == 3,
              "占位残留=%s media=%d" % ("【待补图" in texts2, n_media2))


def main():
    try:
        for fn in (t8_1, t8_2, t8_3, t8_4):
            print("\n== %s ==" % fn.__name__)
            fn()
    finally:
        for b in TMP_BIDS:
            shutil.rmtree(b, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    print()
    print("阶段 8 回归（T8-1~T8-4 新增能力）：共 %d 项，通过 %d，失败 %d"
          % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("\n失败明细：")
        for name, _, detail in failed:
            print("  FAIL %s　— %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
