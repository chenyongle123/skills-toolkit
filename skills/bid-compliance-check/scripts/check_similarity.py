# -*- coding: utf-8 -*-
"""
check_similarity.py —— ② bid-compliance-check 雷同自查机检（②-B · E 类）
计划书 §8.6 / references/雷同自查清单.md。

🔴 唯一实现原则：雷同机检只在本文件一处实现（与 check_consistency.py 同规）。
   ③④ 均不得复制一份——复制两份必然各自演进（v0.9 教训）。

口径（与清单逐条一致）：**只报信号**（密度/结构/命中位置），**不判"是否串标"**——
判权在行政监督部门；本脚本只降低概率，不承诺免责。

⚠️ 实装范围（诚实声明，2026-10-31 核定）**：本套件**无历史稿库**（同套件历史产出
未落库），故清单 §四「与历史稿逐段相似度比对」**不可机检**，产出中显式标注
「未机检，不得视为已查」。可机检的只有**单稿内部**四类：
① 套话密度；② 结构模板化（段落数/段长变异系数、小标题句式复用）；
③ 跨章套话重复；④ 以表代文（图表数 > 正文段落数）。

输入：--bid <项目/bid>（读 00_metadata.json + 01c_format-outline.json + 05_chapters/*.md）
输出：06_compliance/similarity-check.md
rc：0=无 ⚠️ 信号；1=存在 ⚠️ 信号（G5 人工逐条闭环后方可 recheck_confirmed）；2=输入缺失
"""
import argparse
import datetime as _dt
import json
import os
import re
import statistics
import sys
from collections import defaultdict

# —— 阈值（清单称"观察值，非合格线"；此处仅作信号触发线，不作为合格判定）——
TH_CLICHE_RATIO = 0.15   # 单章 套话句数 / 段落数
TH_PARA_CV = 0.15        # 各章段落数变异系数下限（低于＝高度雷同）
TH_LEN_CV = 0.25         # 各章段长中位数变异系数下限
TH_HEAD_SUFFIX = 0.60    # 小标题句式（XX管理/措施/保证…）复用率
TH_CROSS_CH = 3          # 同一句套话出现的章数

# —— 套话模式（清单 §二 + ③ 写作规范禁词）——
CLICHE = [
    (re.compile(r"本着[^，。；]{0,14}?的?(?:原则|宗旨|精神)"), "本着……的原则"),
    (re.compile(r"为了[^，。；]{0,20}?(?:顺利|有效|更好)(?:实施|推进|开展|完成)"), "为了……的顺利实施"),
    (re.compile(r"综上所述"), "综上所述"),
    (re.compile(r"众所周知"), "众所周知"),
    (re.compile(r"高度重视"), "高度重视"),
    (re.compile(r"切实加强"), "切实加强"),
    (re.compile(r"严格落实"), "严格落实"),
    (re.compile(r"进一步完善"), "进一步完善"),
    (re.compile(r"科学组织"), "科学组织"),
    (re.compile(r"完善的管理?体系"), "完善的管理体系"),
]
# 「确保/力争…」是技术标常用词（确保工期/质量），**单句命中不算套话**——
# 清单原意是「无主语承诺句式**堆叠**」，故单独统计、达阈值（≥3 处）才报，避免高误报。
PROMISE = re.compile(r"(?:确保|力争)[^，。；]{2,24}")
TH_PROMISE_STACK = 3
# AI 味：段落以 首先/其次/最后 等开头
TRIAD_HEAD = re.compile(r"^\s*(?:首先|其次|再次|然后|最后|第一|第二|第三|其一|其二|其三)")
DIGIT = re.compile(r"\d")
# 小标题句式后缀（"XX管理""XX措施""XX保证"无限复用）
HEAD_SUFFIX = re.compile(r"(?:管理|措施|保证|保障|方案|制度|体系|流程|机制|办法|计划|预案)$")
HEAD_LINE = re.compile(r"^(?:#{1,6}\s+\S|[（(]?[一二三四五六七八九十\d]{1,3}[）)、.．]\s*\S)")
TABLE_ROW = re.compile(r"^\s*\|")


def parse_chapter(path: str) -> dict:
    """05_chapters/<id>.md → {frontmatter, paragraphs}（与 ④ _common.parse_chapter 同口径）。"""
    text = open(path, encoding="utf-8").read()
    fm, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        body = m.group(2)
        for ln in m.group(1).splitlines():
            mm = re.match(r"^(\s*)([\w]+):\s*(.*)$", ln)
            if mm and not mm.group(1):
                fm[mm.group(2)] = mm.group(3).strip().strip("'\"")
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return {"frontmatter": fm, "paragraphs": paras}


def cv(vals: list):
    """变异系数；样本 <2 或均值为 0 时返回 None（不假装能算）。"""
    if len(vals) < 2:
        return None
    mean = statistics.mean(vals)
    if not mean:
        return None
    return statistics.pstdev(vals) / mean


def cliche_in(text: str) -> list:
    """返回 [(命中原文, 标签)]；按句切分，避免整段重复计数。"""
    hits = []
    for sent in re.split(r"[。；;！!？?\n]", text):
        for pat, label in CLICHE:
            m = pat.search(sent)
            if m:
                hits.append((m.group(0).strip(), label))
                break
    return hits


def analyze(chapters: list) -> dict:
    """chapters = [{"id","number","title","paragraphs"}] → 各类信号。"""
    per_ch, warns, infos = [], [], []
    sent_chapters = defaultdict(set)     # 套话句 → 出现于哪些章
    head_all, head_suffix = [], 0
    para_counts, len_medians = [], []

    for ch in chapters:
        paras = ch["paragraphs"]
        if not paras:
            continue
        lens = [len(re.sub(r"\s", "", p)) for p in paras]
        body = [p for p in paras if not p.lstrip().startswith("#")]
        para_counts.append(len(paras))
        len_medians.append(statistics.median(lens) if lens else 0)

        hits = []
        for p in paras:
            hits.extend(cliche_in(p))
        n_cliche = len(hits)
        ratio = n_cliche / max(1, len(paras))
        n_promise = sum(len(PROMISE.findall(p)) for p in paras)
        for raw, _lab in hits:
            sent_chapters[raw].add(str(ch.get("id", "")))

        # 三段式排比：① 连续 ≥3 段以「首先/其次/最后」开头；② 单段内前三句分别以该类词起头
        # （AI 常把三者写进同一段，只查段首会漏）
        triad_run, run, run_at = 0, 0, 0
        for i, p in enumerate(paras):
            if TRIAD_HEAD.match(p):
                run += 1
                if run >= 3:
                    triad_run, run_at = run, i - run + 1
            else:
                run = 0
        triad_in_para = 0
        if not triad_run:
            for i, p in enumerate(paras):
                sents = [s.strip() for s in re.split(r"[。；;！!？?]", p) if s.strip()]
                if len(sents) >= 3 and all(TRIAD_HEAD.match(s) for s in sents[:3]):
                    triad_in_para = i + 1
                    break
        # 以表代文：按**行**统计表格行（表格在 Markdown 里属同一段落块，按段统计永远 ≤ 段落数）
        n_tbl = sum(1 for p in paras for ln in p.split("\n") if TABLE_ROW.match(ln))
        # 小标题句式复用
        heads = [p for p in paras if HEAD_LINE.match(p) and len(p) <= 40]
        for h in heads:
            head_all.append(h)
            if HEAD_SUFFIX.search(h.rstrip("# ").strip()):
                head_suffix += 1
        # 全篇无一处具体数值
        has_digit = any(DIGIT.search(p) for p in paras)

        per_ch.append({"id": ch.get("id", ""), "number": ch.get("number", ""),
                       "title": ch.get("title", ""), "paras": len(paras),
                       "cliche": n_cliche, "ratio": ratio, "triad_run": triad_run,
                       "triad_at": run_at, "n_tbl": n_tbl, "has_digit": has_digit,
                       "promise": n_promise, "median_len": len_medians[-1]})
        if n_promise >= TH_PROMISE_STACK:
            warns.append(f"无主语承诺句式堆叠：{ch.get('id','')}「确保/力争…」{n_promise} 处"
                         f" ＞ {TH_PROMISE_STACK - 1}（清单 §二：堆叠即提示重写）")
        if ratio > TH_CLICHE_RATIO:
            warns.append(f"套话密度：{ch.get('number','')}{ch.get('title','')}（{ch.get('id','')}）"
                         f"套话 {n_cliche} 处 / 段落 {len(paras)} ＝ {ratio:.0%} ＞ {TH_CLICHE_RATIO:.0%}")
        if triad_run:
            warns.append(f"AI 味排比：{ch.get('id','')} 第 {run_at + 1} 段起连续 {triad_run} 段"
                         f"以「首先/其次/最后」类词开头")
        if triad_in_para:
            warns.append(f"AI 味排比：{ch.get('id','')} 第 {triad_in_para} 段内前三句"
                         f"均以「首先/其次/最后」类词起头（段内排比）")
        if n_tbl > len(body):
            warns.append(f"以表代文：{ch.get('id','')} 表格行 {n_tbl} ＞ 正文段落 {len(body)}")
        if not has_digit:
            infos.append(f"{ch.get('id','')} 全章无一处具体数值（清单 §二「全篇无一处具体数值」）")

    # 结构模板化（章节间）——⚠️ 刻意只作**信息态**、不抬 rc：
    # 按招标「投标文件格式」章写作时，各章篇幅、栏目相近是**常态**（同模板同栏目），
    # CV 低并不等于雷同；若设为 ⚠️ 会造成"每次都报"的常态化误报，反而淹没真信号。
    # 数值照列，由人工结合套话密度、跨章重复、小标题复用等信号综合判断。
    cv_para, cv_len = cv(para_counts), cv(len_medians)
    if cv_para is not None and cv_para < TH_PARA_CV:
        infos.append(f"结构模板化：各章段落数 {para_counts}，变异系数 {cv_para:.2f} ＜ {TH_PARA_CV}"
                     f"（各章篇幅相近属常态，仅作参考，不单独要求重写）")
    if cv_len is not None and cv_len < TH_LEN_CV:
        infos.append(f"结构模板化：各章段长中位数 {[int(x) for x in len_medians]}，"
                     f"变异系数 {cv_len:.2f} ＜ {TH_LEN_CV}（同上，仅作参考）")
    if head_all:
        r = head_suffix / len(head_all)
        if r >= TH_HEAD_SUFFIX:
            warns.append(f"小标题句式复用：{head_suffix}/{len(head_all)} ＝ {r:.0%} 以"
                         f"「管理/措施/保证/方案…」收尾 ＞ {TH_HEAD_SUFFIX:.0%}")
    # 跨章套话重复
    cross = [(s, sorted(c)) for s, c in sent_chapters.items() if len(c) >= TH_CROSS_CH]
    cross.sort(key=lambda kv: -len(kv[1]))
    for s, c in cross[:12]:
        warns.append(f"跨章套话重复：「{s[:40]}」出现于 {len(c)} 章（{'、'.join(c[:6])}"
                     f"{'…' if len(c) > 6 else ''}）")
    return {"per_ch": per_ch, "warns": warns, "infos": infos, "cross": cross,
            "cv_para": cv_para, "cv_len": cv_len,
            "head_total": len(head_all), "head_suffix": head_suffix}


def render(res: dict, bid: str) -> str:
    md = ["# 雷同自查（②-B · E 类机检）", "",
          f"> 生成：bid-compliance-check check_similarity；bid：`{bid}`；"
          f"时间：{_dt.datetime.now().astimezone().replace(microsecond=0).isoformat()}",
          "> 口径：**只报信号（密度/结构/命中位置），不判「是否串标」**——判权在行政监督部门；"
          "本报告只降低概率，不承诺免责。", ""]
    md.append("## 一、套话密度")
    md.append("")
    md.append("| 章节 | 段落数 | 套话处数 | 占比 | 确保/力争 | 具体数值 |")
    md.append("|---|---|---|---|---|---|")
    for c in res["per_ch"]:
        flag = " ⚠️" if c["ratio"] > TH_CLICHE_RATIO else ""
        pflag = " ⚠️" if c.get("promise", 0) >= TH_PROMISE_STACK else ""
        md.append(f"| {c['number']}{c['title']}（`{c['id']}`） | {c['paras']} | {c['cliche']} | "
                  f"{c['ratio']:.0%}{flag} | {c.get('promise', 0)}{pflag} | "
                  f"{'有' if c['has_digit'] else '无'} |")
    md += ["", "## 二、结构模板化（信息态，不单独触发处置）", "",
           "> 各章篇幅/栏目相近在按招标格式章写作时属**常态**，故本节只列数值供人工参考，"
           "不进「需人工处置项」；请结合 §一 套话密度与 §三 跨章重复综合判断。", ""]
    md.append(f"- 各章段落数变异系数 CV＝{res['cv_para'] if res['cv_para'] is None else round(res['cv_para'], 2)}"
              f"（参考阈值 {TH_PARA_CV}；低于阈值＝各章结构高度相近）")
    md.append(f"- 各章段长中位数变异系数 CV＝{res['cv_len'] if res['cv_len'] is None else round(res['cv_len'], 2)}"
              f"（阈值 {TH_LEN_CV}）")
    md.append(f"- 小标题句式复用：{res['head_suffix']}/{res['head_total']}"
              f"（阈值 {TH_HEAD_SUFFIX:.0%}）")
    md += ["", "## 三、跨章套话重复", ""]
    if res["cross"]:
        for s, c in res["cross"][:12]:
            md.append(f"- 「{s[:40]}」→ {len(c)} 章：{'、'.join(c[:6])}{'…' if len(c) > 6 else ''}")
    else:
        md.append("- 无（同一句套话未出现于 ≥3 章）")
    md += ["", "## 四、与历史稿相似段落", "",
           "⚠️ **本项未机检，不得视为已查**：需「历史稿库」（同套件历史产出）做逐段相似度比对，"
           "**本套件暂无该产物**。请人工按 `references/雷同自查清单.md` §四执行："
           "与历史稿逐段比对、命中段**重写而非换序**；与他人公开方案/模板的雷同段一律重写。", "",
           "## 五、独立性自查（G5 必查，制度红线，不可机检）", ""]
    for item in ("本次使用的知识库/账号不含其他投标人数据（跨企业数据隔离红线）",
                 "素材母库中来源不明、无法确认归属的素材未入库使用",
                 "多人协同时，各编制人底稿未混用同一份未清理模板"):
        md.append(f"- [ ] {item}")
    if res["warns"]:
        md += ["", "## 六、⚠️ 需人工处置项", ""]
        for w in res["warns"]:
            md.append(f"- {w}")
    if res["infos"]:
        md += ["", "## 七、信息态", ""]
        for i in res["infos"]:
            md.append(f"- ℹ️ {i}")
    md += ["", "> 处置：命中项须**重写而非换序**（清单 §四）；G5 逐条闭环后方可写 `recheck_confirmed`。"]
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    bid = args.bid
    if not os.path.isdir(bid):
        print(f"【执行阻断】bid 目录不存在：{bid}")
        return 2
    ch_dir = os.path.join(bid, "05_chapters")
    if not os.path.isdir(ch_dir):
        print("【执行阻断】05_chapters/ 缺失（先完成 ③ 正文）")
        return 2
    o1c_p = os.path.join(bid, "01c_format-outline.json")
    outline = json.load(open(o1c_p, encoding="utf-8")) if os.path.exists(o1c_p) else None
    if not outline:
        print("【执行阻断】01c_format-outline.json 缺失（章序基准）")
        return 2
    by_id = {}
    for fn in sorted(os.listdir(ch_dir)):
        if fn.endswith(".md"):
            ch = parse_chapter(os.path.join(ch_dir, fn))
            cid = ch["frontmatter"].get("chapter_id") or fn[:-3]
            by_id[cid] = ch
    chapters = []
    for node in outline.get("chapters", []):
        cid = str(node.get("id", ""))
        if cid in by_id:
            chapters.append({"id": cid, "number": str(node.get("number", "")),
                             "title": str(node.get("title", "")),
                             "paragraphs": by_id[cid]["paragraphs"]})
    if not chapters:
        print("【执行阻断】05_chapters 按 01c 章序装载为空")
        return 2

    res = analyze(chapters)
    out_dir = os.path.join(bid, "06_compliance")
    os.makedirs(out_dir, exist_ok=True)
    out_p = os.path.join(out_dir, "similarity-check.md")
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(render(res, bid))
    n = len(res["warns"])
    print(f"雷同自查：章节 {len(chapters)} 个；⚠️ 需人工处置 {n} 项（报告：{out_p}）")
    for w in res["warns"]:
        print("  ⚠️", w)
    print("ℹ️ 与历史稿相似段落：未机检（无历史稿库），见报告 §四，须人工执行")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
