#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
word_count.py —— ③ 篇幅统计（写作期，对照 04_outline.word_target）
================================================================
定位（计划书 §4.2：篇幅按分值权重分配，不得各章平均用力）：
  每章写完（五步循环步 4）与阶段汇总时跑本脚本，看实际字数对齐目标。

字数口径（③ 自定义，与页数无关）：
  - CJK 字符逐字计 1；
  - 拉丁字母/数字连续串计 1 词（1250A → "1250"+"A"＝2；LGJ-240/30 → 1）；
  - 剔除 frontmatter、[[F:]]/[[S:]]/[[EV:]] 来源标注；
  - Markdown 标记符（# * | - > 等）不计数，标题与表格文字本体计数。

标记：
  MISSING —— 04_outline 有节点而无对应章节文件（未写）；
  ⚠ —— |偏差| > 40%（目标 0 的章不计偏差，仅报实际值）。

边界：只报告、不改写、不替用户调 word_target（目标调整属 ① 目录骨架的 G1 范畴）。
页数估算不属本脚本（页数上限判据归 ④ 装配五项检查，计划书 §8.5.3）。

用法：python word_count.py --bid <项目/bid目录>
退出码：0=正常出表；1=存在 MISSING 未写章或孤儿文件（写作未完成，事实态报出）；
        2=04_outline.json 缺失/不可解析（无目标基准即无从对齐）。
零三方依赖；Python ≥ 3.8。
"""
import argparse
import json
import os
import re
import sys

CHAPTER_FILE = re.compile(r"^(n-[0-9a-f]{4})(?:_.*)?\.md$")
REF = re.compile(r"\[\[(?:F|S|EV):[^\]]*\]\]")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
WORD = re.compile(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*")


def split_frontmatter(text):
    """与 check_facts.py 同口径的独立实现（两脚本互不 import，各自可独立分发）。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def count_text(s):
    """按口径计字数：CJK 逐字 + 拉丁/数字词。来源标注先剔除。"""
    t = REF.sub("", s)
    return len(CJK.findall(t)) + len(WORD.findall(t))


def count_file(path):
    with open(path, encoding="utf-8") as f:
        _, body = split_frontmatter(f.read())
    return count_text(body)


def main():
    ap = argparse.ArgumentParser(description="③ 篇幅统计（对照 04_outline.word_target，只报告不补猜）")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    bid = args.bid

    outline_p = os.path.join(bid, "04_outline.json")
    if not os.path.exists(outline_p):
        print("FAIL 04_outline.json 缺失（无目标基准即无从对齐——先经 ① 生成并过 G1）")
        return 2
    try:
        with open(outline_p, encoding="utf-8") as f:
            chapters = json.load(f).get("chapters", [])
    except (json.JSONDecodeError, OSError) as e:
        print("FAIL 04_outline.json 不可解析：%s" % e)
        return 2
    if not chapters:
        print("FAIL 04_outline.json 无 chapters 节点")
        return 2

    counts = {}
    ch_dir = os.path.join(bid, "05_chapters")
    if os.path.isdir(ch_dir):
        for fn in sorted(os.listdir(ch_dir)):
            m = CHAPTER_FILE.match(fn)
            if m:
                counts[m.group(1)] = count_file(os.path.join(ch_dir, fn))

    known = {c.get("id") for c in chapters}
    orphans = sorted(set(counts) - known)

    tot_a = tot_t = n_missing = 0
    print("%-8s %-4s %-28s %8s %8s %8s  %s" % ("id", "序", "章节（number title）", "实际", "目标", "偏差", "状态"))
    for c in sorted(chapters, key=lambda x: x.get("order", 0)):
        cid = c.get("id", "")
        target = c.get("word_target", 0) or 0
        number = str(c.get("number", ""))
        title = str(c.get("title", ""))
        status = c.get("status", "")
        if cid in counts:
            actual = counts[cid]
            if target > 0:
                dev = (actual - target) * 100.0 / target
                mark = "⚠超偏差" if abs(dev) > 40 else ""
                dev_s = "%+d%%" % round(dev)
            else:
                dev_s, mark = "—", "⚠无目标"
            tot_a += actual
        else:
            actual, dev_s, mark = 0, "—", "MISSING"
            n_missing += 1
        tot_t += target
        print("%-8s %-4s %-28s %8d %8d %8s  %s%s" %
              (cid, number, (number + " " + title)[:26], actual, target, dev_s, status, mark))

    dev_all = "%+d%%" % round((tot_a - tot_t) * 100.0 / tot_t) if tot_t > 0 else "—"
    print("合计：实际 %d / 目标 %d（偏差 %s）｜未写章 %d/%d" %
          (tot_a, tot_t, dev_all, n_missing, len(chapters)))
    if orphans:
        print("注意：05_chapters/ 存在无 outline 节点的文件（不得自行加章，先回 ① 调整骨架）：")
        for o in orphans:
            print("  - %s（%d 字）" % (o, counts[o]))
    print("说明：⚠＝|偏差|>40%；篇幅按分值权重分配（§4.2），高权重章超偏差应优先复核而非平均删补")
    if n_missing or orphans:
        print(f"事实态：存在 MISSING 未写章 {n_missing} 个／孤儿文件 {len(orphans)} 个 → rc=1（写作未完成）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

