# -*- coding: utf-8 -*-
"""
check_consistency.py —— ② bid-compliance-check 跨章一致性检查（②-B，全套件唯一实现）
计划书 §4.3 C 类一致性子项 / 计划书 §5 目录树（③ 不复制，v0.9 已删 ③ 副本）。

🔴 唯一实现原则：跨章一致性只在本文件一处实现；成稿后由 ②-B 调用。
   ① ③ ④ 均不得复制一份——复制两份必然各自演进（v0.9 教训）。

定位（阶段边界）：
- ②-B（成稿后）执行；②-A 不跑本脚本（任务卡层面无正文可比）。
- 本版（v0.3.0）为**骨架实现**：名称/编号类可精确基准比对的全自动；
  金额/日期/工期类只做"跨章取值集合"信号扫描（纯文本无法判定哪些数值
  属同一语义），逐项甄别留待阶段 2 完整交付——**不假装能自动定性**。

口径：只报"不一致出现在哪几处、值分别是多少"，**不替投标人选定正确值**。

输入：--bid <项目/bid>（读 00_metadata.json + 01 + 05_chapters/*.md）
输出：06_compliance/consistency-issues.md
"""
import argparse, json, os, re, sys
from collections import defaultdict

# 金额：数字+单位 / 货币符号 / 中文大写 / 千分位（四类形态，与 M8 B1 同源）
# 注意：不收裸 `\d{4,}`——全文扫描下会把年份（2026）当金额，误报远超收益
AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:万元|元|亿元)|[¥￥]\s*\d[\d,]*(?:\.\d+)?|[零一二三四五六七八九十百千万亿圆整]{2,}")
# 日期：ISO / 中文 / 简写年月日
DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
# 工期：数字+时长单位（不收"XX 年"——会把年份当工期；工期以天/月计）
DURATION = re.compile(r"\d+\s*(?:个)?\s*(?:日历天|天|个月|月)")


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def iter_chapters(bid):
    d = os.path.join(bid, "05_chapters")
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".md"):
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                out.append((fn, f.read()))
    return out


def main():
    ap = argparse.ArgumentParser(description="②-B 跨章一致性检查（骨架版：名称/编号精确比对＋金额/日期/工期信号扫描）")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    bid = args.bid

    meta_p = os.path.join(bid, "00_metadata.json")
    if not os.path.exists(meta_p):
        print("FAIL 缺 00_metadata.json（②-B 前置：stage 必须为 writing）")
        return 2
    meta = load_json(meta_p)
    stage = meta.get("stage")
    if stage != "writing":
        print("FAIL stage=%s，②-B 要求 writing（当前实现仅对成稿生效）" % stage)
        return 2

    chapters = iter_chapters(bid)
    if not chapters:
        print("FAIL 05_chapters/ 无 .md 成稿，无可检查对象")
        return 2

    proj = meta.get("project", {})
    proj_name = (proj.get("name") or "").strip()
    proj_no = (proj.get("no") or "").strip()

    # 1) 名称/编号精确基准比对（全自动）
    # 名称近似变体判据：含基准名主干（前 6 字）但整串不等于基准名、且基准名不在其中；
    # 先剔除**招标人（purchaser）全名**所在的行——purchaser 名与项目名常共前缀
    # （如"中能建投深州…"），不剔会把业主名误报成项目名变体（实测误报）。
    purchaser = (proj.get("purchaser") or "").strip()
    name_hits = defaultdict(list)   # 变体 -> [文件名]
    no_hits = defaultdict(list)
    for fn, text in chapters:
        for line in text.splitlines():
            if purchaser and purchaser in line:
                line = line.replace(purchaser, "＃")  # 置换后不影响其余比对
            # 项目名基准串的"近似变体"：含基准名主干（前 6 字）但不相等的行
            if proj_name and len(proj_name) >= 6:
                stem = proj_name[:6]
                for m in re.finditer(r"[一-龥A-Za-z0-9（）()\-]{8,60}", line):
                    s = m.group(0)
                    if stem in s and s != proj_name and proj_name not in s:
                        name_hits[s].append(fn)
            if proj_no and proj_no not in line:
                for m in re.finditer(r"编号[：:\s写成=为是]*\s*([A-Za-z0-9\-]{4,30})", line):
                    if m.group(1) != proj_no:
                        no_hits[m.group(1)].append(fn)

    # 2) 金额/日期/工期跨章取值集合（信号扫描，不自动定性）
    amounts = defaultdict(set)
    dates = defaultdict(set)
    durations = defaultdict(set)
    for fn, text in chapters:
        for v in AMOUNT.findall(text):
            amounts[re.sub(r"\s+", "", v)].add(fn)
        for v in DATE.findall(text):
            dates[re.sub(r"\s+", "", v)].add(fn)
        for v in DURATION.findall(text):
            durations[re.sub(r"\s+", "", v)].add(fn)

    md = ["# 跨章一致性问题清单（②-B · check_consistency.py v0.3.0 骨架版）", ""]
    md.append("> 输入：00_metadata.json(stage=writing) + 05_chapters/*.md（%d 个成稿）。" % len(chapters))
    md.append("> 口径：只报事实态（值+出现位置），**不替投标人选定正确值**；阶段 2 完整交付前，")
    md.append("> 金额/日期/工期类为**信号扫描**（跨章取值集合），逐项甄别由人工完成。")
    md.append("")
    md.append("## 一、项目名称基准比对")
    md.append("- 基准值（00_metadata.project.name）：`%s`" % (proj_name or "（未载）"))
    if name_hits:
        for v, fns in sorted(name_hits.items()):
            md.append("- ⚠️ 疑似变体「%s」：%s" % (v, "、".join(sorted(set(fns)))))
    else:
        md.append("- ✅ 未发现名称变体")
    md.append("")
    md.append("## 二、招标编号基准比对")
    md.append("- 基准值（00_metadata.project.no）：`%s`" % (proj_no or "（未载）"))
    if no_hits:
        for v, fns in sorted(no_hits.items()):
            md.append("- ⚠️ 疑似异值「%s」：%s" % (v, "、".join(sorted(set(fns)))))
    else:
        md.append("- ✅ 未发现编号异值")
    md.append("")
    md.append("## 三、跨章金额取值集合（信号，人工甄别同一语义）")
    if amounts:
        for v, fns in sorted(amounts.items()):
            md.append("- `%s`：%s" % (v, "、".join(sorted(fns))))
    else:
        md.append("- （无）")
    md.append("")
    md.append("## 四、跨章日期取值集合（信号，人工甄别同一语义）")
    if dates:
        for v, fns in sorted(dates.items()):
            md.append("- `%s`：%s" % (v, "、".join(sorted(fns))))
    else:
        md.append("- （无）")
    md.append("")
    md.append("## 五、跨章工期取值集合（信号，人工甄别同一语义）")
    if durations:
        for v, fns in sorted(durations.items()):
            md.append("- `%s`：%s" % (v, "、".join(sorted(fns))))
    else:
        md.append("- （无）")
    md.append("")
    md.append("## 六、G5 提示")
    md.append("- 本章所有 ⚠️ 项须逐条人工闭环后方可写 `recheck_confirmed`；")
    md.append("- 集合中出现**同语义多值**（如两个不同的投标总价）即跨章不一致，按计划书 §4.3 C 类上报。")

    out_d = os.path.join(bid, "06_compliance")
    os.makedirs(out_d, exist_ok=True)
    p = os.path.join(out_d, "consistency-issues.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    n_issue = len(name_hits) + len(no_hits)
    print("OK", p)
    print("名称/编号疑点：%d 项；金额取值 %d 个、日期 %d 个、工期 %d 个（信号，待人工甄别）"
          % (n_issue, len(amounts), len(dates), len(durations)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
