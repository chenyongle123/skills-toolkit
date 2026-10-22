#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_facts.py —— ③ bid-technical-proposal 事实引用核验（写作期实时，阶段 2）
======================================================================
定位（计划书 §4.4 五步循环步 4 的机检卡点；铁律 1/7/8 的可执行判据）：
  章节草稿交背对背复核（步 5）前必须跑本脚本，rc=1 不得交复核。

检查项：
  E1 未知事实引用：[[F:id]] 的 id 不在 02_facts（优先 yaml；缺则 md 仅做存在性）
  E2 未知评分点引用：[[S:id]] 的 id 不在 01_tender-facts.json 的 scoring.items[].id
  E3 无来源段落：正文段（空行分隔）无任何 [[F:]]/[[S:]] 标注
     豁免——整段仅为占位（【待填…】/【待确认…】/[[EV:…]]，无实质文字）
     降级——单行、不含数字的过渡句按警告报（反例 7：过渡句限单句、不承载事实）
  E4 引用了缺 source 字段的事实条目（facts.schema.yaml R1：缺 source 不得进交付稿）
  W1 被引用事实 updated_at 超 12 个月（R2：引用须提示，不得静默使用；仅 yaml 可关联时）
  W2 事实条目可识别但未能逐字段解析（只保存在性检查，建议核查 02_facts.yaml 格式）

不做的事（边界）：
  - 不判废标、不给法律结论（铁律 4）；
  - 不解析 02_facts.md 的人读表格做字段级深检（md 仅存在性，深检以 yaml 为准）；
  - [[EV:…]] 只计数不校验（03b 索引属 ④ 阶段 3 装配，见计划书 §8.5.3）。

用法：
  python check_facts.py --bid <项目/bid目录> [--chapter n-3a2f]
退出码：0=通过（可有警告）；1=有错误；2=输入缺失/不可解析。

零三方依赖（可移植性是产品需求）；Python ≥ 3.8。
"""
import argparse
import json
import os
import re
import sys
from datetime import date, timedelta

REF_F = re.compile(r"\[\[F:((?:qual|perf|pers|eq|fin)-\d{3,})\]\]")
REF_S = re.compile(r"\[\[S:([^\]\s]+)\]\]")
REF_EV = re.compile(r"\[\[EV:[^\]]*\]\]")
PLACEHOLDER = re.compile(r"【(?:待填|待确认|能力未实现)[^】]*】")
FACT_ID_ANY = re.compile(r"\b(?:qual|perf|pers|eq|fin)-\d{3,}\b")
CHAPTER_FILE = re.compile(r"^(n-[0-9a-f]{4})(?:_.*)?\.md$")
SECTIONS = ("qualifications", "performances", "personnel", "equipment", "financials")


def _scalar(v):
    """YAML 标量宽容转换：去引号 → bool → int → 原串。解析不了的留给上层按串处理。"""
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def split_frontmatter(text):
    """把章节文件拆成 (frontmatter 原文, 正文)。无 frontmatter 返回 ("", text)。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def parse_frontmatter(fm_text):
    """解析 chapter.schema.json 固定形状的 frontmatter（零依赖手写，不装 PyYAML）。

    支持两级：顶层 key: value；g4 嵌套块（缩进 2 空格）；route_summary 列表（- 条目）。
    只服务本套件约定的字段形状，不追求通用 YAML。
    """
    out, cur_key, in_g4, in_list = {}, None, False, False
    for line in fm_text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        indented = line[:1] in (" ", "\t")
        stripped = line.strip()
        if in_list and stripped.startswith("- "):
            out["g4"]["route_summary"].append(_scalar(stripped[2:]))
            continue
        if in_list and not stripped.startswith("- "):
            in_list = False
        if stripped.startswith("- ") and cur_key == "route_summary":
            out["g4"]["route_summary"].append(_scalar(stripped[2:]))
            in_list = True
            continue
        if in_g4 and not indented:
            in_g4 = False
        m = re.match(r"^(\w+):\s*(.*)$", stripped)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if indented and in_g4:
            if val == "":
                out["g4"][key] = [] if key == "route_summary" else {}
                cur_key = key
                in_list = key == "route_summary"
            else:
                out["g4"][key] = _scalar(val)
        elif not indented:
            if val == "":
                if key == "g4":
                    out[key] = {}
                    in_g4 = True
                else:
                    out[key] = None
            else:
                out[key] = _scalar(val)
            cur_key = key
    return out


def _parse_flow_item(inner):
    """解析行内流式条目 `- {id: qual-002, name: …, source: "…"}` 的字段对。"""
    fields = {}
    for m in re.finditer(r"(\w+)\s*:\s*(\"[^\"]*\"|'[^']*'|[^,{}]+)", inner):
        fields[m.group(1)] = _scalar(m.group(2))
    return fields


def load_facts(bid):
    """读事实库。返回 (facts: {id: fields|None}, mode)。

    优先 02_facts.yaml（facts.schema.yaml：冲突以 yaml 为准）：
      逐行跟踪 section/item/field，块式与行内流式条目均支持；
      解析不到字段的 id 记 None（存在但未解析，只保 E1 存在性，报 W2）。
    缺 yaml 时退 02_facts.md：正则扫 id 做存在性（mode='md'，字段级深检跳过）。
    """
    yaml_p = os.path.join(bid, "02_facts.yaml")
    md_p = os.path.join(bid, "02_facts.md")
    if os.path.exists(yaml_p):
        with open(yaml_p, encoding="utf-8") as f:
            lines = f.read().splitlines()
        facts, cur, section = {}, None, None
        for line in lines:
            m = re.match(r"^(\w+):\s*$", line)
            if m:
                section, cur = m.group(1), None
                continue
            if section not in SECTIONS:
                continue
            flow = re.match(r"^\s*-\s*\{(.*)\}\s*$", line)
            if flow:
                fields = _parse_flow_item(flow.group(1))
                if fields.get("id"):
                    facts[str(fields["id"])] = fields
                cur = None
                continue
            if re.match(r"^\s*-\s+", line):
                m2 = re.match(r"^\s*-\s*(\w+):\s*(.*)$", line)
                cur = {}
                if m2:
                    cur[m2.group(1)] = _scalar(m2.group(2))
                    if m2.group(1) == "id":
                        facts[str(cur["id"])] = cur
                continue
            if cur is not None:
                m3 = re.match(r"^\s*([A-Za-z_]+):\s*(.*)$", line)
                if m3 and m3.group(2).strip():
                    cur[m3.group(1)] = _scalar(m3.group(2))
                    if m3.group(1) == "id" and str(cur["id"]) not in facts:
                        facts[str(cur["id"])] = cur
        # 存在性兜底：解析遗漏的 id 由全文正则补齐（宁报 W2 不误报 E1）
        for i in FACT_ID_ANY.findall(open(yaml_p, encoding="utf-8").read()):
            facts.setdefault(i, None)
        return facts, "yaml"
    if os.path.exists(md_p):
        with open(md_p, encoding="utf-8") as f:
            text = f.read()
        return {i: None for i in FACT_ID_ANY.findall(text)}, "md"
    return None, "missing"


def load_scoring_ids(bid):
    p = os.path.join(bid, "01_tender-facts.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return {str(it.get("id")) for it in data.get("scoring", {}).get("items", [])}


def iter_blocks(body):
    """正文按空行切段。产出 (起始行号, 段文本)。纯标题段（# 开头）不参与来源判定。"""
    blocks, start, buf = [], None, []
    for idx, line in enumerate(body.splitlines(), 1):
        if line.strip():
            if start is None:
                start = idx
            buf.append(line)
        elif buf:
            blocks.append((start, "\n".join(buf)))
            start, buf = None, []
    if buf:
        blocks.append((start, "\n".join(buf)))
    return blocks


def _excerpt(s, n=40):
    s = re.sub(r"\s+", " ", s)
    return s[:n] + ("…" if len(s) > n else "")


def _is_placeholder_only(block):
    """段内剔除 [[EV:]] 与【待填/待确认】占位后无实质文字（无 CJK、无字母数字）即占位段。"""
    t = REF_EV.sub("", block)
    t = PLACEHOLDER.sub("", t)
    t = re.sub(r"[\s|#*\-:>`]+", "", t)
    return not re.search(r"[\u3400-\u4dbf\u4e00-\u9fffA-Za-z0-9]", t)


def check_chapter(path, facts, facts_mode, scoring_ids, today):
    """单章核验。返回 (errors, warnings, 统计)。"""
    errs, warns = [], []
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, body = split_frontmatter(text)
    meta = parse_frontmatter(fm)
    cid = meta.get("chapter_id") or os.path.basename(path)
    n_f = n_s = n_ev = 0

    for rid in REF_F.findall(body):
        n_f += 1
        if rid not in facts:
            errs.append(f"[E1] 未知事实引用 [[F:{rid}]]（不在 02_facts）")
        else:
            fields = facts[rid]
            if fields is None:
                if facts_mode == "yaml":
                    warns.append(f"[W2] 事实 {rid} 可识别但未解析出字段（建议核查 02_facts.yaml 格式）")
            else:
                if not str(fields.get("source", "") or "").strip():
                    errs.append(f"[E4] 事实 {rid} 缺 source（R1：缺 source 不得进交付稿）")
                up = str(fields.get("updated_at", "") or "").strip()
                if up:
                    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", up)
                    if m:
                        try:
                            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                            if today - d > timedelta(days=365):
                                warns.append(f"[W1] 事实 {rid} updated_at={up} 超 12 个月（R2：引用须提示）")
                        except ValueError:
                            warns.append(f"[W2] 事实 {rid} updated_at={up!r} 非法日期")
    for sid in REF_S.findall(body):
        n_s += 1
        if sid not in scoring_ids:
            errs.append(f"[E2] 未知评分点引用 [[S:{sid}]]（不在 01.scoring.items）")
    n_ev = len(REF_EV.findall(body))

    for ln, block in iter_blocks(body):
        if all(l.lstrip().startswith("#") for l in block.splitlines() if l.strip()):
            continue  # 纯标题段
        if REF_F.search(block) or REF_S.search(block):
            continue
        if _is_placeholder_only(block):
            continue
        if len(block.splitlines()) == 1 and not re.search(r"[%％]|\d", block):
            warns.append(f"[W1] 过渡句（单句无数字，无来源标注）L{ln}：{_excerpt(block)}")
        else:
            errs.append(f"[E3] 无来源段落 L{ln}：{_excerpt(block)}")
    return errs, warns, (n_f, n_s, n_ev, meta)


def main():
    ap = argparse.ArgumentParser(description="③ 事实引用核验（写作期实时；铁律 1/7/8 的机检判据）")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--chapter", default=None, help="只检单章（chapter_id，如 n-3a2f）")
    args = ap.parse_args()
    bid = args.bid
    if not os.path.isdir(os.path.join(bid, "05_chapters")):
        print("FAIL 05_chapters/ 不存在（③ 无章节可检——先按五步循环产出章节草稿）")
        return 2
    facts, fmode = load_facts(bid)
    if facts is None:
        print("FAIL 02_facts.yaml / 02_facts.md 均缺失（③ 前置产物，缺一即拒）")
        return 2
    scoring_ids = load_scoring_ids(bid)
    if scoring_ids is None:
        print("FAIL 01_tender-facts.json 缺失（评分点引用核验的基准）")
        return 2

    files = []
    for fn in sorted(os.listdir(os.path.join(bid, "05_chapters"))):
        m = CHAPTER_FILE.match(fn)
        if m and (args.chapter is None or m.group(1) == args.chapter):
            files.append((m.group(1), os.path.join(bid, "05_chapters", fn)))
    if not files:
        print("FAIL 05_chapters/ 无 n-xxxx 命名章节文件（%s）" %
              ("过滤条件：" + args.chapter if args.chapter else "命名须为 <chapter_id>.md"))
        return 2

    today = date.today()
    n_err = n_warn = tot_f = tot_s = tot_ev = 0
    for cid, path in files:
        errs, warns, (n_f, n_s, n_ev, meta) = check_chapter(path, facts, fmode, scoring_ids, today)
        tot_f, tot_s, tot_ev = tot_f + n_f, tot_s + n_s, tot_ev + n_ev
        if errs or warns:
            label = "%s（%s %s）" % (cid, meta.get("number", ""), meta.get("title", ""))

            print("== " + label)
            for e in errs:
                print("  " + e)
            for w in warns:
                print("  " + w)
        n_err += len(errs)
        n_warn += len(warns)

    print("汇总：%d 章｜事实引用 %d 条、评分点引用 %d 条、EV 标记 %d 处｜错误 %d、警告 %d（事实库：%s）"
          % (len(files), tot_f, tot_s, tot_ev, n_err, n_warn, fmode))
    if n_err:
        print("FAIL 存在错误：E1/E2/E3/E4 任一未清零，不得交背对背复核（五步循环步5 前置）")
        return 1
    print("PASS 无来源段落与未知引用均已清零" + ("（含 %d 条警告，逐条人工确认后可继续）" % n_warn if n_warn else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())




