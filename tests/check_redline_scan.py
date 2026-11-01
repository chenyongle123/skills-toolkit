#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_redline_scan.py —— 提交红线机检（AGENTS.md:54 七类，零三方依赖）

用法：
    python tests/check_redline_scan.py [--dict <词表.json>] [--root <仓库根>]

做什么：
  扫**全量被 git 跟踪的文件**（`git ls-files`，不是"本轮改动的 blob"），
  按 AGENTS.md:54 红线做模式级检测。

为什么必须扫全量：
  v1.7.49 的取证只作用于 `git diff --cached`，而携带真实指代的文件往往本轮
  未改动、不在增量内 —— 这正是 2026-11-01 实测漏网的根因（parse_spec_items.py）。
  只扫增量无法支撑"清零"结论。

检测项（R1–R6 为模式级，零词表即可跑；R7 需外部词表）：
  R1 本机绝对路径 / Windows 用户名   —— 盘符路径、/Users/<名>/
  R2 场址经纬度                       —— 北纬/东经 + 数字、NNN.NNNNNN°
  R3 文号 / 招标编号                  —— 〔20xx〕N号、发文机关简称 + 编号
  R4 高速口（带编号形态）             —— XX高速（Gxxxx）
  R5 招标原文逐条抄录（启发式）       —— raw_text 字段 + 段号锚点（Pxxxx）
  R6 金额（暂定价 / 控制价上下文）    —— 暂估价/控制价 + 金额
  R7 县市名 / 乡镇村名 / 单位名 / 业主名 / 项目名 —— 需 --dict，无词表时
     **明确输出"未检，不得视为已查"，不谎报已扫描**

退出码：
  0 = 无命中（或仅有已豁免项）
  1 = 有命中（逐条给「文件·行号·类别·片段」）
  2 = 结构性阻断：不在 git 仓库内 / git 不可用 / --dict 文件不可读

设计约束（本脚本自身的合规要求）：
  ① 词表不入库 —— 词表经 --dict 从仓库外传入，缺省即"未检"；
  ② 命中片段**只输出前 40 字符**，不整行回显，避免"为证明已清除而二次泄漏"；
  ③ 豁免清单只放行公开信息（GitHub URL、版权署名、测试夹具虚构路径）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

MAX_SNIPPET = 40


def _snippet(s):
    s = s.strip()
    return s[:MAX_SNIPPET] + ("…" if len(s) > MAX_SNIPPET else "")


# ---------- 检测规则：(类别, 说明, 编译后的正则) ----------
RULES = [
    ("R1", "本机绝对路径/盘符",
     re.compile(r"[A-Za-z]:[\\/](?:Users|用户|workbuddy|WorkBuddy)[\\/]"
                r"|/[Uu]sers/[A-Za-z0-9._-]+/")),
    ("R2", "场址经纬度",
     re.compile(r"(?:北纬|东经|N|E)\s?\d{2,3}[.．]\d{2,}"
                r"|\d{2,3}[.．]\d{4,}\s?°")),
    ("R3", "招标编号/标段编号",
     re.compile(r"(?:招标|项目|标段|备案|采购)\s?编号\s*[:：]?\s*[A-Za-z0-9][A-Za-z0-9-]{5,}"
                r"|\b[A-Z]{2,6}[-—]\d{4}[-—]\d{2,4}\b")),
    # 注：`〔20xx〕N号` 形态**不作独立检项** —— 公开法律法规文号（法释〔2020〕25号、
    # 建质〔2017〕138号…）属必须保留的公开信息，按形态无法与内部发文区分
    # （实测 53 处误报全为此类）。内部发文机关简称归入 R7 词表类处理。
    ("R4", "高速口（带编号）",
     re.compile(r"[一-龥]{2,6}高速\s*[（(]\s?[GSG]\d{2,4}\s*[)）]")),
    ("R5", "招标原文抄录（段号锚点）",
     # 加长度门槛：raw_text 值须 ≥60 字符才计命中 —— 测试夹具的合成短串
     # （如 raw_text: "……（P3337）"）属合规代号，不计（实测误报来源之一）。
     re.compile(r"raw_text\W{0,12}[\"']?[^\"']{60,600}?[（(]\s?P\d{3,4}\s*[)）]")),
    ("R6", "暂定价/控制价金额",
     re.compile(r"(?:暂估价|暂定价|控制价|最高限价)[^。；\n]{0,30}?"
                r"\d[\d,，]*(?:\.\d+)?\s?(?:万元|元|亿元)")),
]

# ---------- 豁免：仅放行公开信息 ----------
EXEMPT = [
    re.compile(r"github\.com/[\w.-]+"),          # 仓库克隆地址（公开）
    re.compile(r"^\s*Copyright|版权|署名"),       # 版权署名
    re.compile(r"C:\\Users\\tester\\"),          # 测试夹具虚构路径
    re.compile(r"tests/check_redline_scan\.py"),  # 本脚本自身
]

# 片段级豁免：命中片段本身属「合规代号 / 公开标准编号」时不计命中。
# 例：GF-2017-0201（国家示范文本编号，公开）、SAMPLE-/DEMO-/CEZB-/HT-（测试夹具代号，
# 符合 AGENTS.md 连带约束①「测试夹具的编号必须用代号」）。
EXEMPT_FRAGMENT = [
    re.compile(r"\b(?:GF|SAMPLE|DEMO|CEZB|HT|TEST|ISO|GB|JCT)[-—]\d{4}[-—]\d{2,6}\b"),
]


def tracked_files(root):
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                             capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    return names


def scan(root, dict_words=None):
    files = tracked_files(root)
    if files is None:
        print("【结构性阻断】git ls-files 失败：不在 git 仓库内或 git 不可用")
        return 2, [], []

    hits, skipped = [], []
    for rel in files:
        p = os.path.join(root, rel)
        if os.path.basename(p) in (".gitignore",):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                lines = f.read().split("\n")
        except (OSError, UnicodeDecodeError, ValueError):
            skipped.append(rel)
            continue
        for i, line in enumerate(lines, 1):
            if any(e.search(line) for e in EXEMPT):
                continue
            for code, desc, rx in RULES:
                m = rx.search(line)
                if m:
                    frag = m.group(0)
                    if any(x.search(frag) for x in EXEMPT_FRAGMENT):
                        continue
                    hits.append((rel, i, code, desc, _snippet(frag)))
                    break
        if dict_words:
            for i, line in enumerate(lines, 1):
                for w in dict_words:
                    if w and w in line:
                        hits.append((rel, i, "R7", "词表命中", _snippet(w)))
                        break
    rc = 1 if hits else 0
    return rc, hits, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description="提交红线机检（AGENTS.md:54 七类）")
    ap.add_argument("--root", default=None, help="仓库根（默认：本文件上级目录）")
    ap.add_argument("--dict", default=None,
                    help="外部词表 JSON（字符串数组；不入库，从仓库外传入）")
    ns = ap.parse_args(argv)

    here = os.path.dirname(os.path.abspath(__file__))
    root = ns.root or os.path.normpath(os.path.join(here, ".."))

    words = None
    if ns.dict:
        try:
            with open(ns.dict, encoding="utf-8") as f:
                words = json.load(f)
            if not isinstance(words, list):
                print("【结构性阻断】--dict 必须是字符串数组")
                return 2
        except (OSError, ValueError) as e:
            print("【结构性阻断】--dict 不可读：%s" % e)
            return 2

    rc, hits, skipped = scan(root, words)

    print("== 提交红线机检（AGENTS.md:54）==")
    print("扫描对象：git ls-files 全量被跟踪文件（根目录 %s）" % root)
    print("模式级检项：R1 路径/用户名、R2 经纬度、R3 招标编号、R4 高速口、"
          "R5 原文抄录、R6 暂定价金额")
    if words:
        print("词表级检项：R7 已启用（%d 词）" % len(words))
    else:
        print("词表级检项：R7（县市名/乡镇村名/单位名/业主名/项目名）"
              "**未检，不得视为已查** —— 词表不入库，需 --dict 从仓库外传入")

    if skipped:
        print("跳过（二进制或不可解码）：%d 个文件" % len(skipped))

    if hits:
        print("命中 %d 处：" % len(hits))
        for rel, ln, code, desc, snip in hits[:50]:
            print("  %s:%d  [%s %s]  %s" % (rel, ln, code, desc, snip))
        if len(hits) > 50:
            print("  ……（其余 %d 处省略）" % (len(hits) - 50))
        print("处置：按 AGENTS.md:54 代号化后重跑；不得以「属测试夹具」为由放行"
              "（连带约束①：测试夹具亦须用代号）")
    else:
        print("命中 0 处（模式级 R1–R6 全清）")
    return rc


if __name__ == "__main__":
    sys.exit(main())
