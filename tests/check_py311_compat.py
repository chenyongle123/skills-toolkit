#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/check_py311_compat.py — Python 3.11 语法／API 兼容扫描（零三方依赖）

背景（2026-11-01 真实事故）：
  CI 的 `python-version` 是 **3.11**，开发机是 **3.13**。
  `tools/select_facts.py` 在 f-string 的 `{}` 内写了转义引号 `\\"\\"`，
  属 **PEP 701** 才放开的写法（3.12+）。结果：
    本机 3.13 → 正常；CI 3.11 → `SyntaxError: f-string expression part
    cannot include a backslash` → stage6 全红。
  这类问题**在本机永远跑不出来**，必须靠静态扫描拦住。

检项：
  C1  f-string 的 {} 内出现反斜杠（PEP 701，3.12+ 才允许）
  C2  f-string 的 {} 内出现与外层同类型的引号（3.12+ 才允许）
  C3  已知的 3.12+/3.13+ 才有的 API／语法（清单法，见 FORBIDDEN_312）

用法：python tests/check_py311_compat.py（rc 0=通过，1=有命中，2=用法/扫描异常）
已知局限：
  - C1/C2 用逐行状态机近似解析，**不解析嵌套 f-string 与多行字符串**；
    复杂写法可能漏报。它拦的是"高频踩坑"，不等于完整的 3.11 语法校验。
  - 权威判定仍以 CI 上真实 3.11 解释器为准。
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("tools", "tests", "skills")

# 3.12+/3.13+ 才有的 API／语法（清单随踩坑补充）
FORBIDDEN_312 = (
    # 注意：只匹配"调用形态"，避免误伤 os.walk(路径) 这类 3.x 一直存在的 API
    ("itertools.batched", re.compile(r"\bitertools\.batched\b"),
     "itertools.batched（3.12+）"),
    ("Path.walk", re.compile(r"\.walk\s*\(\s*\)"), "Path.walk()（3.12+，无参调用）"),
    ("os.process_cpu_count", re.compile(r"\bprocess_cpu_count\s*\("),
     "os.process_cpu_count（3.13+）"),
    ("PEP695 type 语句", re.compile(r"^\s*type\s+\w+\s*="), "PEP 695 type 语句（3.12+）"),
    ("typing.override", re.compile(r"@override\b|typing\.override\b"),
     "typing.override（3.12+）"),
)

# 本文件内含上述正则的字符串字面量，会被自己命中 → 跳过自身
SELF_NAME = "check_py311_compat.py"


def _fstring_spans(line):
    """提取一行内所有 f-string 字面量（近似）：返回 [(外层引号, 字符串体)]。

    只处理单行、非嵌套的常见写法；三引号与跨行 f-string 不在覆盖范围内。
    """
    out = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "f" and i + 1 < n and line[i + 1] in "\"'":
            # 确认是字符串前缀而非标识符的一部分
            if i > 0 and (line[i - 1].isalnum() or line[i - 1] in "_."):
                i += 1
                continue
            quote = line[i + 1]
            j = i + 2
            body = []
            while j < n:
                c = line[j]
                if c == "\\":
                    body.append(line[j:j + 2])
                    j += 2
                    continue
                if c == quote:
                    break
                body.append(c)
                j += 1
            out.append((quote, "".join(body)))
            i = j + 1
            continue
        i += 1
    return out


def scan_file(path, rel):
    hits = []
    lines = io.open(path, encoding="utf-8", errors="replace").read().split("\n")
    for lineno, line in enumerate(lines, 1):
        if "f\"" not in line and "f'" not in line:
            pass
        for quote, body in _fstring_spans(line):
            for expr in re.findall(r"\{([^{}]*)\}", body):
                if "\\" in expr:
                    hits.append((rel, lineno, "C1",
                                 "f-string 的 {} 内含反斜杠（3.11 SyntaxError）",
                                 expr.strip()[:40]))
                elif quote in expr:
                    hits.append((rel, lineno, "C2",
                                 "f-string 的 {} 内含与外层同型引号（3.11 不允许）",
                                 expr.strip()[:40]))
        for _name, rx, desc in FORBIDDEN_312:
            if rx.search(line):
                hits.append((rel, lineno, "C3", "疑似 3.12+ 特性：" + desc,
                             line.strip()[:40]))
    return hits


def main():
    hits = []
    files = 0
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for dp, dn, fn in os.walk(str(base)):
            if "__pycache__" in dp:
                continue
            for f in sorted(fn):
                if not f.endswith(".py") or f == SELF_NAME:
                    continue
                p = os.path.join(dp, f)
                files += 1
                hits.extend(scan_file(p, os.path.relpath(p, ROOT)))
    print("Python 3.11 兼容扫描：%d 个 .py 文件" % files)
    print("检项：C1 f-string {} 内反斜杠 / C2 f-string {} 内同型引号 / C3 3.12+ API 清单")
    if hits:
        print("\n命中 %d 处（CI 用 Python 3.11，以下写法会 SyntaxError 或 AttributeError）：" % len(hits))
        for rel, lineno, code, desc, snip in hits:
            print("  %s:%d  [%s] %s — %s" % (rel, lineno, code, desc, snip))
        return 1
    print("命中 0 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
