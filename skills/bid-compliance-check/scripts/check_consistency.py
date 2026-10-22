# -*- coding: utf-8 -*-
"""
check_consistency.py —— ② bid-compliance-check 跨章一致性检查（②-B，全套件唯一实现）
计划书 §4.3 C 类一致性子项 / 计划书 §5 目录树（③ 不复制，v0.9 已删 ③ 副本）。

🔴 唯一实现原则：跨章一致性只在本文件一处实现；成稿后由 ②-B 调用。
   ① ③ ④ 均不得复制一份——复制两份必然各自演进（v0.9 教训）。

v0.4.0（阶段 2）升级（#7 欠账 / 计划书 §11.3 G5 前置第 1 条口径）：
- 位置粒度：所有报告项给「章节（number title，id）· 第 N 段 · L 行：原文片段」；
- 同语义多值检测（⚠️ 疑似跨章不一致）：工期/金额按「语义类 + 单位族」分组，
  组内出现 ≥2 个不同值即报（如总工期 180 日历天 vs 150 日历天、投标总价 5000 万 vs 4800 万）；
  同数值不同写法（5000万元 vs 50000000元 vs 人民币伍仟万元整）归一化后只记
  「同值异形」信号，不报不一致（中文大写金额内置数值解析，避免投标函大/小写并书误报）；
- 退出码：0=无疑似不一致；1=存在 ⚠️ 项（G5 人工逐条闭环后方可 recheck_confirmed）；2=输入缺失。

口径：只报"不一致出现在哪几处、值分别是多少"，**不替投标人选定正确值**。

输入：--bid <项目/bid>（读 00_metadata.json + 05_chapters/*.md）
输出：06_compliance/consistency-issues.md
"""
import argparse, json, os, re, sys
from collections import OrderedDict, defaultdict

# 金额：数字+单位 / 货币符号 / 中文大写（含大写数字） / 千分位（四类形态，与 M8 B1 同源）
# 注意：不收裸 `\d{4,}`——全文扫描下会把年份（2026）当金额，误报远超收益
AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:万元|元|亿元)|[¥￥]\s*\d[\d,]*(?:\.\d+)?|[零壹一二贰三叁肆四伍五陆六柒七捌八玖九拾十佰百仟千万亿圆元整]{2,}")
# 日期：ISO / 中文 / 简写年月日
DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
# 工期：数字+时长单位（不收"XX 年"——会把年份当工期；工期以天/月计）
DURATION = re.compile(r"\d+\s*(?:个)?\s*(?:日历天|天|个月|月)")
# 工期语义类关键词（不命中归 ""＝未归类，只做信号罗列）
CTX_DURATION = re.compile(r"工期|完工|竣工|建成|投产")
# 金额语义类
CTX_AMOUNT = OrderedDict([
    ("总价", re.compile(r"投标总价|总报价|投标金额|报价总额|含税总价|投标总报价")),
    ("保证金", re.compile(r"投标保证金|履约保证金|保证金金额")),
])
# 中文数字归一（大写→小写）
_CN_NORM = str.maketrans("壹贰叁肆伍陆柒捌玖拾佰仟", "一二三四五六七八九十百千")
_CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _cn_section(seg):
    """『三千五百』→ 3500（十百千权位；空段返 0，非法字符返 None）。"""
    if not seg:
        return 0
    total, num = 0, 0
    for ch in seg:
        if ch in _CN_DIGIT:
            num = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            total += (num or 1) * _CN_UNIT[ch]
            num = 0
        else:
            return None
    return total + num


def parse_cn_amount(s):
    """中文金额串 → 元（float）。如「人民币伍仟万元整」→ 5e7。失败返 None。

    先归一大写数字，再按 亿/万 分节从右往左累乘权位。
    """
    t = re.sub(r"人民币|圆|元|整|零", "", s).translate(_CN_NORM)
    if not t or not re.fullmatch(r"[一二三四五六七八九十百千万亿]+", t):
        return None
    parts = re.split(r"([万亿])", t)  # 交替：[段, 权, 段, 权, …, 段]
    yuan, m, i = 0.0, 1, len(parts) - 1
    seg = _cn_section(parts[i])
    if seg is None:
        return None
    yuan += seg
    i -= 1
    while i >= 1:
        mu = parts[i]
        seg = _cn_section(parts[i - 1])
        if seg is None:
            return None
        m *= {"万": 1e4, "亿": 1e8}[mu]
        yuan += seg * m
        i -= 2
    return yuan if yuan else None


def amount_to_yuan(raw):
    """金额原文 → 元（float）。数字+单位/货币符号/中文大写三类；失败返 None。"""
    s = re.sub(r"\s+", "", raw)
    if re.fullmatch(r"[¥￥][\d,]+(?:\.\d+)?", s):
        return float(s[1:].replace(",", ""))
    m = re.fullmatch(r"([\d,]+(?:\.\d+)?)(亿元|万元|元)", s)
    if m:
        v = float(m.group(1).replace(",", ""))
        return v * {"亿元": 1e8, "万元": 1e4, "元": 1}[m.group(2)]
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", s):
        return float(s.replace(",", ""))
    return parse_cn_amount(raw)


def unit_family_of_duration(raw):
    """工期值 → 单位族：day（日历天/天）/ month（个月/月）。"""
    s = re.sub(r"\s+", "", raw)
    return "month" if ("个" in s or s.endswith("月")) else "day"


class Chapter:
    """成稿章节：frontmatter 元数据 + 逐行段落定位。"""

    def __init__(self, fn, text):
        self.fn = fn
        self.cid = fn[:-3] if fn.endswith(".md") else fn
        self.number, self.title = "", ""
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
        if m:
            for ln in m.group(1).splitlines():
                mm = re.match(r'^(chapter_id|number|title):\s*(.+)\s*$', ln)
                if mm:
                    v = mm.group(2).strip().strip('"').strip("'")
                    setattr(self, mm.group(1), v)
            if getattr(self, "chapter_id", ""):
                self.cid = self.chapter_id
            body = text[m.end():]          # frontmatter 剥离，正文单独扫
            # 正文首行对应的文件绝对行号（m.end() 前的换行数 +1）
            self.body_offset = text[:m.end()].count("\n")
        else:
            body = text
            self.body_offset = 0
        self.body_lines = body.splitlines()
        # 逐行段落号（空行分块；同一段内各行同号，段号从 1 起，空行记 0）
        self.para_of = []
        n, in_block = 0, False
        for ln in self.body_lines:
            if ln.strip():
                if not in_block:
                    n += 1
                    in_block = True
                self.para_of.append(n)
            else:
                in_block = False
                self.para_of.append(0)

    def label(self):
        t = " ".join(x for x in (self.number, self.title) if x)
        if t:
            return "「%s」（%s）" % (t, self.cid)
        return "（%s）" % (self.fn if self.fn != self.cid + ".md" else self.cid)

    def locate(self, line_idx):
        """line_idx 0 起（正文相对）→ （段落号, 文件绝对行号 1 起, 该行片段）。"""
        ln = self.body_lines[line_idx] if line_idx < len(self.body_lines) else ""
        excerpt = re.sub(r"\s+", " ", ln.strip())
        if len(excerpt) > 60:
            excerpt = excerpt[:60] + "…"
        return self.para_of[line_idx], self.body_offset + line_idx + 1, excerpt


def iter_chapters(bid):
    """读 05_chapters/*.md → [Chapter]（按文件名排序）。"""
    d = os.path.join(bid, "05_chapters")
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".md"):
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                out.append(Chapter(fn, f.read()))
    return out


def fmt_loc(chapter, line_idx):
    """出现位置 → 「章节 · 第 N 段 · L 行：片段」。"""
    para, lineno, excerpt = chapter.locate(line_idx)
    return "%s · 第 %d 段 · L%d：%s" % (chapter.label(), para, lineno, excerpt)


def scan_occurrences(chapters, regex):
    """全章扫描 regex → [(Chapter, line_idx, 命中原文)]。"""
    out = []
    for ch in chapters:
        for i, ln in enumerate(ch.body_lines):
            if regex.search(ln):
                for m in regex.finditer(ln):
                    out.append((ch, i, m.group(0)))
    return out


def group_duration(chapters):
    """工期出现 → 分组 {(单位族, 语义类): {规范化值: [位置…]}}。

    语义类：""＝未归类（信号）；"工期"＝行内含工期/完工/竣工等词（参与 ⚠️ 判定）。
    扫描前先剔除行内日期（「2026年12月15日」中的「12月」不是工期）。
    """
    groups = defaultdict(lambda: defaultdict(list))
    for ch in chapters:
        for i, ln in enumerate(ch.body_lines):
            for m in DURATION.finditer(DATE.sub("", ln)):
                v = re.sub(r"\s+", "", m.group(0))
                fam = unit_family_of_duration(m.group(0))
                ctx = "工期" if CTX_DURATION.search(ln) else ""
                groups[(fam, ctx)][v].append(fmt_loc(ch, i))
    return groups


def group_amount(chapters):
    """金额出现 → 分组 {语义类: {"values": {规范化值: [位置]}, "nums": {元值: [写法]}}}。

    语义类：总价/保证金/""未归类。数值可归一的以元值比对（同值异形不报 ⚠️，
    记「写法差异」）；归一失败的按原文串比对。
    """
    groups = defaultdict(lambda: {"values": defaultdict(list), "nums": defaultdict(list)})
    for ch, i, raw in scan_occurrences(chapters, AMOUNT):
        v = re.sub(r"\s+", "", raw)
        line = ch.body_lines[i]
        ctx = next((k for k, rx in CTX_AMOUNT.items() if rx.search(line)), "")
        yuan = amount_to_yuan(raw)
        g = groups[ctx]
        g["values"][v].append(fmt_loc(ch, i))
        if yuan is not None:
            g["nums"][round(yuan, 2)].append(v)
    return groups


def scan_name_variants(chapters, proj_name, purchaser):
    """项目名近似变体扫描（v0.3.0 口径保留）→ {变体: [位置…]}。

    变体判据：行内长串含基准名主干（前 6 字）但整串≠基准名、且基准名不在其中；
    招标人全名所在的行先置换剔除（业主名与项目名常共前缀，实测误报）。
    """
    hits = defaultdict(list)
    if not proj_name or len(proj_name) < 6:
        return hits
    stem = proj_name[:6]
    for ch in chapters:
        for i, ln in enumerate(ch.body_lines):
            if purchaser and purchaser in ln:
                ln = ln.replace(purchaser, "＃")
            for m in re.finditer(r"[一-龥A-Za-z0-9（）()\-]{8,60}", ln):
                s = m.group(0)
                if stem in s and s != proj_name and proj_name not in s:
                    hits[s].append(fmt_loc(ch, i))
    return hits


def scan_no_variants(chapters, proj_no):
    """招标编号异值扫描（v0.3.0 口径保留）→ {异值: [位置…]}。"""
    hits = defaultdict(list)
    if not proj_no:
        return hits
    for ch in chapters:
        for i, ln in enumerate(ch.body_lines):
            if proj_no in ln:
                continue
            for m in re.finditer(r"编号[：:\s写成=为是]*\s*([A-Za-z0-9\-]{4,30})", ln):
                if m.group(1) != proj_no:
                    hits[m.group(1)].append(fmt_loc(ch, i))
    return hits


def group_dates(chapters):
    """日期出现（信号）→ {规范化值: [位置…]}。"""
    groups = defaultdict(list)
    for ch, i, raw in scan_occurrences(chapters, DATE):
        groups[re.sub(r"\s+", "", raw)].append(fmt_loc(ch, i))
    return groups


# 关键日期槽（C4 口径 A）：同槽跨章多值 → ⚠️ 抬 rc=1；排期类日期仍为信号不判。
DATE_SLOTS = [
    ("截止", re.compile(r"(投标截止|截标|递交截止|提交截止|截止)")),
    ("开标", re.compile(r"(开标|开启时间)")),
    ("递交", re.compile(r"(递交|提交|送达)")),
    ("有效期", re.compile(r"(有效期至?|到期日?)")),
]
DATE_SLOT_RE = re.compile(
    r"(\d{4}\s*[年\-.]\s*\d{1,2}\s*[月\-.]\s*\d{1,2}\s*日?|\d{4}-\d{1,2}-\d{1,2})")


def group_date_slots(chapters):
    """关键日期槽 → {槽名: {规范化日期: [位置…]}}。"""
    groups = defaultdict(lambda: defaultdict(list))
    for ch in chapters:
        for i, ln in enumerate(ch.body_lines):
            for slot, rx in DATE_SLOTS:
                m = rx.search(ln)
                if not m:
                    continue
                # 槽词后 40 字内取首个日期（同槽跨章取值应一致）
                seg = ln[m.end():m.end() + 40]
                dm = DATE_SLOT_RE.search(seg)
                if dm:
                    v = re.sub(r"\s+", "", dm.group(1))
                    groups[slot][v].append(fmt_loc(ch, i))
                break
    return groups


def main():
    ap = argparse.ArgumentParser(description="②-B 跨章一致性检查（v0.4.0：位置粒度＋工期/金额同语义多值检测）")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    bid = args.bid

    meta_p = os.path.join(bid, "00_metadata.json")
    if not os.path.exists(meta_p):
        print("FAIL 缺 00_metadata.json（②-B 前置：stage 必须为 writing/rechecking）")
        return 2
    meta = load_json(meta_p)
    stage = meta.get("stage")
    if stage not in ("writing", "rechecking"):
        print("FAIL stage=%s，②-B 要求 writing/rechecking（仅对成稿生效）" % stage)
        return 2

    chapters = iter_chapters(bid)
    if not chapters:
        print("FAIL 05_chapters/ 无 .md 成稿，无可检查对象")
        return 2

    proj = meta.get("project", {})
    proj_name = (proj.get("name") or "").strip()
    proj_no = (proj.get("no") or "").strip()
    purchaser = (proj.get("purchaser") or "").strip()

    name_hits = scan_name_variants(chapters, proj_name, purchaser)
    no_hits = scan_no_variants(chapters, proj_no)
    dur_groups = group_duration(chapters)
    amt_groups = group_amount(chapters)
    date_groups = group_dates(chapters)

    n_warn = len(name_hits) + len(no_hits)
    dur_warn = [(k, vs) for k, vs in dur_groups.items()
                if k[1] == "工期" and len(vs) >= 2]
    amt_warn = []
    for ctx, g in amt_groups.items():
        if not ctx:
            continue
        distinct = {v for v in g["values"]}
        n_norm = sum(len(ws) for ws in g["nums"].values())  # 可归一的写法数（归一失败不进 nums）
        if len(g["nums"]) <= 1 and n_norm == len(distinct) and len(distinct) >= 2:
            # 全部写法可数值归一且归一后同值 → 同值异形，不报 ⚠️
            # （n_norm<distinct 即存在归一失败写法：混入未归一值时不得按同值放行）
            continue
        if len(g["nums"]) >= 2 or (len(distinct) >= 2 and not g["nums"]):
            amt_warn.append((ctx, g))
    # C4（口径 A）：关键日期槽（开标/截止/递交/有效期）同槽多值 → ⚠️ 抬 rc；
    # 其余日期仍为信号罗列（排期类日期多值属正常，不进判定）
    date_slots = group_date_slots(chapters)
    date_warn = {slot: vs for slot, vs in date_slots.items() if len(vs) >= 2}
    n_warn += len(dur_warn) + len(amt_warn) + len(date_warn)

    md = ["# 跨章一致性问题清单（②-B · check_consistency.py v0.4.0）", ""]
    md.append("> 输入：00_metadata.json(stage=%s) + 05_chapters/*.md（%d 个成稿）。" % (stage, len(chapters)))
    md.append("> 口径：只报事实态（值＋出现位置），**不替投标人选定正确值**；")
    md.append("> ⚠️＝同语义多值（疑似跨章不一致，G5 人工闭环）；同值异形（如 5000万元 vs 人民币伍仟万元整）不报 ⚠️。")
    md.append("")
    md.append("## 一、项目名称基准比对")
    md.append("- 基准值（00_metadata.project.name）：`%s`" % (proj_name or "（未载）"))
    if name_hits:
        for v, locs in sorted(name_hits.items()):
            md.append("- ⚠️ 疑似变体「%s」：" % v)
            for loc in locs:
                md.append("    - %s" % loc)
    else:
        md.append("- ✅ 未发现名称变体")
    md.append("")
    md.append("## 二、招标编号基准比对")
    md.append("- 基准值（00_metadata.project.no）：`%s`" % (proj_no or "（未载）"))
    if no_hits:
        for v, locs in sorted(no_hits.items()):
            md.append("- ⚠️ 疑似异值「%s」：" % v)
            for loc in locs:
                md.append("    - %s" % loc)
    else:
        md.append("- ✅ 未发现编号异值")
    md.append("")
    md.append("## 三、跨章工期取值（按「单位族＋语义类」分组；⚠️＝同语义多值）")
    if dur_groups:
        for (fam, ctx), vs in sorted(dur_groups.items()):
            head = "%s·%s" % (fam, ctx or "未归类")
            mark = " ⚠️ **疑似跨章不一致（同语义多值，G5 须逐条闭环）**" if (ctx == "工期" and len(vs) >= 2) else ""
            md.append("- 【%s】%s" % (head, mark))
            for v, locs in sorted(vs.items()):
                md.append("    - `%s`（%d 处）：" % (v, len(locs)))
                for loc in locs:
                    md.append("        - %s" % loc)
    else:
        md.append("- （无）")
    md.append("")
    md.append("## 四、跨章金额取值（按语义类分组；⚠️＝同语义多值；同值异形仅信号）")
    if amt_groups:
        for ctx, g in sorted(amt_groups.items()):
            head = ctx or "未归类"
            mark = " ⚠️ **疑似跨章不一致（同语义多值，G5 须逐条闭环）**" if (ctx, g) in amt_warn else ""
            md.append("- 【%s】%s" % (head, mark))
            for v, locs in sorted(g["values"].items()):
                md.append("    - `%s`（%d 处）：" % (v, len(locs)))
                for loc in locs:
                    md.append("        - %s" % loc)
            same_num = {n: ws for n, ws in g["nums"].items() if len(set(ws)) >= 2}
            if same_num:
                for n, ws in sorted(same_num.items()):
                    md.append("    - ℹ️ 同值异形：%s 元，写法 %s（数值一致，不报不一致）" % (n, "／".join(sorted(set(ws)))))
    else:
        md.append("- （无）")
    md.append("")
    md.append("## 五、跨章日期取值（信号，人工甄别同一语义）")
    if date_warn:
        md.append("- ⚠️ **关键日期槽多值（开标/截止/递交/有效期须全稿一致，G5 须逐条闭环）：**")
        for slot in sorted(date_warn):
            md.append("  - 【%s】" % slot)
            for v, locs in sorted(date_warn[slot].items()):
                md.append("    - `%s`（%d 处）：" % (v, len(locs)))
                for loc in locs:
                    md.append("        - %s" % loc)
        md.append("")
    if date_groups:
        for v, locs in sorted(date_groups.items()):
            md.append("- `%s`（%d 处）：" % (v, len(locs)))
            for loc in locs:
                md.append("    - %s" % loc)
    else:
        md.append("- （无）")
    md.append("")
    md.append("## 六、G5 提示")
    md.append("- 本章所有 ⚠️ 项须逐条人工闭环后方可写 `recheck_confirmed`；")
    md.append("- 集合中出现**同语义多值**（如两个不同的投标总价）即跨章不一致，按计划书 §4.3 C 类上报；")
    md.append("- 未归类（行内无工期/总价类关键词）的取值仅作信号罗列，不触发 ⚠️。")

    out_d = os.path.join(bid, "06_compliance")
    os.makedirs(out_d, exist_ok=True)
    p = os.path.join(out_d, "consistency-issues.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("OK", p)
    print("疑似跨章不一致（⚠️ 同语义多值）：名称变体 %d、编号异值 %d、工期组 %d、金额组 %d、关键日期槽 %d；"
          % (len(name_hits), len(no_hits), len(dur_warn), len(amt_warn), len(date_warn)))
    print("日期取值 %d 个（信号）。位置粒度：章节（number title，id）· 第 N 段 · L 行：原文片段。"
          % len(date_groups))
    if n_warn:
        print("FAIL 存在 ⚠️ 项：G5 人工逐条闭环后方可写 recheck_confirmed")
        return 1
    print("PASS 未发现疑似跨章不一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
