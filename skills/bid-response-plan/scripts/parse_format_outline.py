# -*- coding: utf-8 -*-
"""
parse_format_outline.py —— ① bid-response-plan 格式章抽取（01c）
计划书 §5 目录树 / 计划书 §6.2（01c_format-outline.json 契约）。

定位：01c 不是从招标原文**自动解析**得来的（本套件 ① 不读招标原文，
计划书 §3.2 边界）——章节树是**按本项目招标文件「投标文件格式」章
（格式章——章序因项目而异）人工逐字抽取后固化**的常量；本脚本负责把它
序列化为 01c 产物并做保真自检提示。
typography（排版要求）自 v0.25.0 起改为从 ⓪ 01_tender-facts.json 的
blind_format（暗标专项 8 项）派生——修复 D4 缺陷（旧版发空串常量且虚标
source=tender_required，导致 ④ 招标档整档静默回落基线）；blind_format 缺失
时如实标 baseline；提取失败的字段置空并警告（空值在 ④ 招标档会被阻断）。

🔴 保真规则（v0.3.0 加固，验收记录 #2 实测缺陷）：编号与章节名**逐字照录**——
   ① 原文档编号不连续时（如技术标 1、2、7–12）**不得连续化重排**；
   ② 章节名中的括号说明（如「项目实施方案（由投标人自行编制）」）**不得删除**；
   ③ 换项目覆盖 FORMAT_CHAPTERS 常量后，必须跑
      scripts/verify_format_chapters.py 与抽取结果比对，全部逐字一致方可采用。

独立用法：python parse_format_outline.py --bid <项目>/bid [--out 01c_format-outline.json]
"""
import argparse, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- 01c 章节树（本项目「投标文件格式」章逐字） ----------
FORMAT_CHAPTERS = [
    # (id, number, title, level)
    ("n-1001", "一", "商务标", 2),
    ("n-1101", "1", "投标函格式", 3),
    ("n-1102", "2", "投标保证金格式", 3),
    ("n-1103", "3", "法定代表人身份证明", 3),
    ("n-1104", "4", "授权委托书", 3),
    ("n-1105", "5", "商务偏差声明函", 3),
    ("n-1106", "6", "资格审查文件", 3),
    ("n-1111", "6.1", "投标人基本情况表", 4),
    ("n-1112", "6.2", "财务及资信状况", 4),
    ("n-1113", "6.3", "投标人资格声明格式", 4),
    ("n-1114", "6.4", "制造商的资格声明格式", 4),
    ("n-1115", "6.5", "其它资料", 4),
    ("n-1107", "7", "业绩", 3),
    ("n-1121", "7.1", "已完工的业绩表", 4),
    ("n-1122", "7.2", "正在实施的和新承接的项目情况表", 4),
    ("n-1108", "8", "分包或外购情况表", 3),
    ("n-1131", "8.1", "施工分包情况表（适用于投标人不具备招标文件所要求的施工资质的情况）", 4),
    ("n-1132", "8.2", "设计分包情况表（适用于投标人不具备招标文件所要求的设计资质的情况）", 4),
    ("n-1133", "8.3", "主要设备、材料备选供应商名单", 4),
    ("n-1134", "8.4", "备品备件情况一览表", 4),
    ("n-1135", "8.5", "专用工具情况一览表", 4),
    ("n-1136", "8.6", "进口设备/部件情况一览表", 4),
    ("n-1137", "8.7", "外购设备/部件情况一览表", 4),
    ("n-1109", "9", "招标文件要求提供的其他材料", 3),
    ("n-2001", "二", "技术标", 2),
    ("n-2101", "1", "承包人建议书", 3),
    ("n-2102", "2", "项目实施方案（由投标人自行编制）", 3),
    ("n-2103", "7", "技术偏差声明函", 3),
    ("n-2104", "8", "货物主要技术指标和性能的详细说明", 3),
    ("n-2105", "9", "系统设备技术性能检验大纲", 3),
    ("n-2106", "10", "主要设备的产品说明、技术参数、质保声明等", 3),
    ("n-2107", "11", "关键技术响应", 3),
    ("n-2108", "12", "其他招标文件技术规范要求投标人提供或编写的资料", 3),
    ("n-3001", "三", "价格标", 2),
    ("n-3101", "1", "报价要求", 3),
    ("n-3102", "2", "价格说明", 3),
    ("n-3103", "3", "报价表", 3),
    ("n-3111", "3.1", "报价汇总表", 4),
    ("n-3112", "3.2", "施工辅助工程报价表", 4),
    ("n-3113", "3.3", "设备及安装工程报价表", 4),
    ("n-3114", "3.4", "建筑工程费用报价表", 4),
    ("n-3115", "3.5", "其他费用报价表", 4),
]
CID = {t: i for (i, _, t, _) in FORMAT_CHAPTERS}

# ---------- 章节树真实派生（Todo 10 第 2 批：常量仅兜底） ----------
# 派生源 = bid 根 _headings_*.json（人工从招标文件「投标文件格式」章抽取，
# verify_format_chapters 同源格式）：{source, headings: [{page, number, title, level}]}。
# 层级由人工标注（level 正整数、最浅层=1）：number 形态跨项目语义冲突
# （「一」在 A/D 基为顶级、C 基为二级），机器不猜层级（铁律：只报告差异）。
# id 机械分配（重放可复现、与冻结常量序列天然区分）：
#   第 g 个 level=1 条目（组头）→ n-{g}000；组内第 c 条（level≥2）→ n-{g}{c:03d}。


def _check_headings(doc, src):
    """headings 文档契约校验 → 错误列表（空列表=通过）。

    契约：headings 非空数组；每条含 title（非空）与 level（正整数，
    bool 不算）；最浅层 level=1。缺 level 即拒——层级语义由人负责。
    """
    hs = doc.get("headings") if isinstance(doc, dict) else None
    if not isinstance(hs, list) or not hs:
        return ["%s：无非空 headings 数组" % src]
    errs = []
    for i, h in enumerate(hs, 1):
        lv = h.get("level") if isinstance(h, dict) else None
        if (not isinstance(h, dict) or isinstance(lv, bool) or not isinstance(lv, int)
                or lv < 1 or not str(h.get("title") or "").strip()):
            errs.append("%s：第 %d 条缺 level（正整数）或 title（层级由人工标注，机器不猜）"
                        % (src, i))
    if not errs:
        lv_min = min(h["level"] for h in hs)
        if lv_min != 1:
            errs.append("%s：最浅层须标 level=1（当前最小 %d）" % (src, lv_min))
    return errs


def load_headings(bid):
    """扫 bid 根 _headings_*.json → (文档或 None, 状态, 附加信息)。

    状态：none=无文件（FORMAT_CHAPTERS 兜底）；one=恰一份（真实派生）；
    multi=多份（须人工指定，fail-loud）；bad=文件在但契约校验不过。
    """
    files = sorted(glob.glob(os.path.join(bid, "_headings_*.json"))) if bid else []
    if not files:
        return None, "none", []
    if len(files) > 1:
        return None, "multi", files
    try:
        with open(files[0], encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, "bad", ["%s：文件不可读（%s）" % (files[0], e)]
    errs = _check_headings(doc, files[0])
    if errs:
        return None, "bad", errs
    return doc, "one", files


def derive_chapters(doc):
    """headings 文档 → 01c chapters 序列（id 机械分配，重放可复现）。

    level=1 开新组（第 g 组组头 id=n-{g}000）；组内条目按出现顺序
    c=1.. 分配 n-{g}{c:03d}（十进制 3 位，容量 999）。01c 的 level 语义
    与冻结常量对齐（组头=2、组内=3+，即 headings level+1）。page 照录。
    """
    out, g, c = [], 0, 0
    for h in doc["headings"]:
        if h["level"] == 1:
            g, c = g + 1, 0
            cid = "n-%d%03d" % (g, 0)
        else:
            c += 1
            cid = "n-%d%03d" % (g, c)
        if g > 9 or c > 999:
            if all(x["level"] == 1 for x in doc["headings"]):
                raise ValueError(
                    "纯平铺树（%d 条全 level=1）：无组头，id 组序无从分配。"
                    "请在 _headings_*.json 中补 level=1 组头（可用格式章原文标题，"
                    "如「第X章 投标文件格式」）并把条目降为 level=2；"
                    "或删除该文件走 FORMAT_CHAPTERS 常量兜底＋人工裁剪 BUSINESS_FORMS"
                    % len(doc["headings"]))
            raise ValueError("id 容量溢出（组 %d 序 %d）——组头超过 9 个或组内超过 999 条，须人工核查" % (g, c))
        out.append({"id": cid, "number": str(h.get("number") or "").strip(),
                    "title": str(h.get("title") or "").strip(),
                    "level": h["level"] + 1,
                    "page": str(h.get("page") or "").strip() or "n/a-无分页"})
    return out


# ---------- 章节锚定上下文（v0.26.0：03 卡锚定的单一真源=当前 01c 章节树） ----------
# 默认=冻结常量树（独立用法兼容）；build_bid_plan 链在 build_01c 之后、
# build_03 之前调 set_chapter_context 切到当前树（派生/兜底与 01c/04 同源），
# 防止 03 卡 chapter_id 指向常量树而与派生 01c/04 脱钩。


def chapter_map(chapters):
    """章节树 → {title: id}；同题多条取首条（歧义章名不逐字锚定，走语义槽）。"""
    m = {}
    for c in chapters or []:
        t = str(c.get("title") or "").strip()
        if t and t not in m:
            m[t] = c["id"]
    return m


def top_slots(chapters):
    """顶级组头 → 语义槽 {商务/技术/价格/报价: 组头 id}。

    组头判定=level==2 且后随更深层级（子节点）——平铺树全部同级、无组头
    → 空槽（锚定将 fail-loud，不猜——平铺树的卡锚定须人工定方案，机械
    规则无解时不静默挂错章）。组头若无子节点（紧跟同级章），视同平铺条
    目、不占槽，防「商务偏差声明函」一类普通章名冒充组头。
    """
    cl = list(chapters or [])
    slots = {}
    for i, c in enumerate(cl):
        if c.get("level") != 2:
            continue
        nxt = cl[i + 1] if i + 1 < len(cl) else None
        if not (nxt and nxt.get("level", 0) > 2):
            continue
        t = str(c.get("title") or "")
        for kw in ("商务", "技术", "价格", "报价"):
            if kw in t and kw not in slots:
                slots[kw] = c["id"]
    return slots


_CHAPTER_CTX = {"cmap": {t: i for (i, _, t, _) in FORMAT_CHAPTERS},
                "slots": top_slots([{"id": i, "number": n, "title": t, "level": lv}
                                    for (i, n, t, lv) in FORMAT_CHAPTERS])}


def set_chapter_context(chapters):
    """锚定上下文切到当前 01c 章节树（build_bid_plan 链在 build_01c 后调用）。"""
    _CHAPTER_CTX["cmap"] = chapter_map(chapters)
    _CHAPTER_CTX["slots"] = top_slots(chapters)


def resolve_chapter_id(title):
    """启发式章名 → 当前树 chapter_id。

    ① 唯一逐字命中 → 该 id；② 未命中/歧义 → 语义槽（商务/技术/价格/报价
    关键词推导，默认商务槽；价格↔报价同义互备——评分项「价格标」可落
    格式章「报价文件」组头，反之亦然）；③ 槽空 → None（调用方 fail-loud）。
    """
    t = str(title or "").strip()
    if t in _CHAPTER_CTX["cmap"]:
        return _CHAPTER_CTX["cmap"][t]
    kw = next((k for k in ("商务", "技术", "价格", "报价") if k in t), "商务")
    sid = _CHAPTER_CTX["slots"].get(kw)
    if sid is None and kw in ("价格", "报价"):
        sid = _CHAPTER_CTX["slots"].get("报价" if kw == "价格" else "价格")
    return sid


def chapter_known(title):
    """启发式章名是否逐字命中当前锚定上下文（build_task_cards 折叠判断用）。"""
    return str(title or "").strip() in _CHAPTER_CTX["cmap"]


def chapter_id_exact(title):
    """当前锚定上下文逐字命中的 chapter_id（无则 None；不做槽推导——
    商务表挂接等「必须逐字」场景用，validate 过后调用保证非 None）。"""
    return _CHAPTER_CTX["cmap"].get(str(title or "").strip())


def chapter_context_titles():
    """当前锚定上下文全部章名（锚定失败报错时列给人工，限长防刷屏）。"""
    return "、".join(sorted(_CHAPTER_CTX["cmap"])) or "（空树）"


def chapter_context_titles_list():
    """当前锚定上下文全部章名（list；difflib 近邻候选等按序消费用）。"""
    return sorted(_CHAPTER_CTX["cmap"])


# ---------- typography 派生（v0.25.0，D4 根修复：⓪ blind_format → 01c） ----------
# 前 8 字段与 ⓪ 暗标专项 8 项一一对应（schema：字体→font_body/字号→size_body/
# 行距→line_spacing/页边距→margins/页码规则→page_number/页数上限→page_limit/
# 身份标识禁项→identity_ban；语境·适用范围→scope）；indent/binding/seal 为
# 套件扩展、⓪ 侧无对应键 → 置空（④ 按基线取值，来源如实标 baseline）。
# blind_format 缺失/为空 → source=baseline（普通标无暗标格式块属正常，不虚标）。
# 值一律照录原文串（铁律 1：不替招标改写）；④ 负责归一解析（字号/行距/页边距/
# 页码/页限），解析规则与 ④ build_style_profile 同步演进。

_FW_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_FONT_WORDS = ("仿宋_GB2312", "华文宋体", "Times New Roman", "微软雅黑",
               "宋体", "仿宋", "黑体", "楷体", "等线", "Arial")
_SIZE_WORDS = ("初号", "小初", "一号", "小一", "二号", "小二", "三号", "小三",
               "四号", "小四", "五号", "小五", "六号", "小六")
_BLIND_KEYS = ("字体", "字号", "行距", "页边距", "页码规则", "页数上限", "身份标识禁项")


def _clause(text, kw):
    """取第一个含 kw 的子句（按 ；;。，, 切分）；无则 None。"""
    for seg in re.split(r"[；;。，,]", str(text or "")):
        if kw in seg:
            return seg
    return None


def _body_font(val):
    """从「字体」值提取正文字体名：优先「正文」子句内首个字体词；
    无「正文」子句且全值仅一个字体词 → 视为全局字体；其余置空（④ 将阻断）。"""
    if not val:
        return ""
    seg = _clause(val, "正文")
    if seg is not None:
        for w in _FONT_WORDS:
            if w in seg:
                return w
        return ""
    hits = [w for w in _FONT_WORDS if w in val]
    return hits[0] if len(hits) == 1 else ""


def _canon_size(seg):
    """子句 → 规范字号词：优先「(小?)N号」整词（防「四号」误中「小四号」子串），
    退回字号词表（长词优先），再退 Npt/N磅；取不到 None。"""
    m = re.search(r"(小?[一二三四五六初])号", seg)
    if m:
        w = m.group(1)
        key = w if w.startswith("小") else w + "号"
        if key in _SIZE_WORDS:
            return key
    for k in sorted(_SIZE_WORDS, key=len, reverse=True):
        if k in seg:
            return k
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:pt|磅)", seg)
    if m and 5 <= float(m.group(1)) <= 42:
        return m.group(0)
    return None


def _body_size(size_val, font_val=""):
    """从「字号」值提取正文字号：优先「正文」子句；无「正文」子句且全值仅一个
    字号词 → 全局字号；「字号」键缺 → 从「字体」值的「正文」子句提（如
    「正文小四号宋体」→ 小四）；其余置空（④ 将阻断）。"""
    for src, need_clause in ((size_val, False), (font_val, True)):
        if not src:
            continue
        seg = _clause(src, "正文")
        if seg is not None:
            got = _canon_size(seg)
            if got:
                return got
        elif not need_clause:
            hits = [k for k in sorted(_SIZE_WORDS, key=len, reverse=True) if k in src]
            if len(hits) == 1:
                return hits[0]
    return ""


def _page_limit(val):
    """从「页数上限」值提取整数页限：全角数字归一后全值仅一个数字 → 取之；
    0 个或多个数字 → None（不猜，人工核对）。"""
    t = str(val or "").translate(_FW_DIGITS)
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if len(nums) == 1:
        v = float(nums[0])
        if v == int(v) and v >= 1:
            return int(v)
    return None


def _identity_ban(val):
    """「身份标识禁项」→ 字符串数组：剥「不得出现/禁止…」类前缀后按 、，切分，
    逐项照录子串（已是数组的原样清洗）。"""
    if isinstance(val, (list, tuple)):
        return [str(x).strip() for x in val if str(x).strip()]
    t = str(val or "").strip()
    if not t:
        return []
    t = re.sub(r"^(?:不得|不应|禁止|严禁)?(?:出现以下|出现|含有|包含|列出)?", "", t)
    items = [s.strip() for s in re.split(r"[、，,]", t) if s.strip()]
    return items or [t]


def _scope(bf):
    """语境/适用范围含「技术」→ technical_only（暗标格式块多限定技术标）。"""
    txt = "".join(str(bf.get(k) or "") for k in ("语境", "适用范围"))
    return "technical_only" if "技术" in txt else "full_doc"


def derive_typography(facts, warn=True):
    """从 ⓪ 01_tender-facts.json（dict）派生 typography。

    blind_format 存在 → source=tender_required、8 项一对一映射照录；
    缺失/为空 → 全项空值 + source=baseline（如实标档，不虚标 tender_required）。
    """
    bf = facts.get("blind_format") if isinstance(facts, dict) else None
    if not isinstance(bf, dict) or not bf:
        if warn:
            print("⚠️ 01_tender-facts 无 blind_format（或为空）——typography 整体按 baseline 档"
                  "（普通标无暗标格式块属正常；招标明示过排版/暗标格式的，回 ⓪ 核对抽取）")
        return {"scope": "full_doc", "font_body": "", "size_body": "", "line_spacing": "",
                "margins": "", "page_number": "", "page_limit": None, "identity_ban": [],
                "indent": "", "binding": "", "seal": "", "source": "baseline"}
    warns = []
    for k in _BLIND_KEYS:
        if not str(bf.get(k) or "").strip():
            warns.append(f"blind_format 缺「{k}」键——对应 01c 字段置空（④ 招标档将阻断，回 ⓪ 核对）")
    font_val = str(bf.get("字体") or "").strip()
    size_val = str(bf.get("字号") or "").strip()
    font = _body_font(font_val)
    if font_val and not font:
        warns.append(f"字体「{font_val}」未能提取正文字体——01c.font_body 置空（④ 招标档将阻断）")
    size = _body_size(size_val, font_val)
    if (size_val or font_val) and not size:
        warns.append("字号未能提取正文字号——01c.size_body 置空（④ 招标档将阻断）")
    limit = _page_limit(bf.get("页数上限"))
    if str(bf.get("页数上限") or "").strip() and limit is None:
        warns.append(f"页数上限「{bf.get('页数上限')}」未能唯一定值——page_limit 按 null"
                     "（未载明）处理，请人工核对")
    typo = {
        "scope": _scope(bf),
        "font_body": font,
        "size_body": size,
        "line_spacing": str(bf.get("行距") or "").strip(),
        "margins": str(bf.get("页边距") or "").strip(),
        "page_number": str(bf.get("页码规则") or "").strip(),
        "page_limit": limit,
        "identity_ban": _identity_ban(bf.get("身份标识禁项")),
        "indent": "",   # 套件扩展，⓪ 暗标 8 项无对应键 → 置空（④ 回落基线 2 字符）
        "binding": "",  # 同上
        "seal": "",     # 同上
        "source": "tender_required",
    }
    if warn:
        for w in warns:
            print("⚠️", w)
    return typo


def build_01c(facts=None, headings=None, warn=True):
    """序列化 01c_format-outline.json（契约 0.2，assets/format-outline.schema.json）。

    headings（load_headings 的 one 态文档或等价 dict，须过 _check_headings）
    非空 → 章节树从人工抽取的格式章标题真实派生（derive_chapters）；
    None → FORMAT_CHAPTERS 冻结常量兜底（仅常量母项目逐字一致，其余项目
    必须补 _headings_*.json 后重跑 ①）。
    typography = derive_typography(facts)（v0.25.0 起从 ⓪ blind_format 派生）。
    """
    if headings:
        chapters = derive_chapters(headings)
    else:
        chapters = [
            {"id": i, "number": n, "title": t, "level": lv, "page": "n/a-无分页"}
            for (i, n, t, lv) in FORMAT_CHAPTERS
        ]
        if warn:
            print("⚠️ 章节树按 FORMAT_CHAPTERS 冻结常量兜底——常量是单项目结构，"
                  "非本项目真实格式章；请人工抽取 bid 根 _headings_*.json（含 level）后重跑 ①")
    return {
        "schema_version": "0.2",
        "chapters": chapters,
        "typography": derive_typography(facts, warn=warn),
    }


def main():
    ap = argparse.ArgumentParser(
        description="生成 01c_format-outline.json（章节树：bid 根 _headings_*.json 真实派生，"
                    "无抽取时 FORMAT_CHAPTERS 常量兜底；排版：⓪ blind_format 派生）")
    ap.add_argument("--bid", help="项目 bid 目录（与 --out 二选一；读 01_tender-facts.json 派生 typography，"
                    "扫 _headings_*.json 派生章节树）")
    ap.add_argument("--out", help="输出文件路径（与 --bid 二选一；无 01 可读时 typography 按 baseline）")
    ap.add_argument("--headings", help="显式指定 headings JSON（缺省自动扫 bid 根 _headings_*.json，恰一份时派生）")
    args = ap.parse_args()
    if not args.bid and not args.out:
        ap.error("必须指定 --bid 或 --out")
    facts = None
    if args.bid:
        fp = os.path.join(args.bid, "01_tender-facts.json")
        if os.path.exists(fp):
            try:
                with open(fp, encoding="utf-8") as f:
                    facts = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️ 01_tender-facts.json 不可读（{e}）——typography 按 baseline 档")
        else:
            print("⚠️ 未找到 01_tender-facts.json——typography 按 baseline 档（链内运行时 ① 总装会先过 gate）")
    hd, state, info = None, "none", []
    if args.headings:
        try:
            with open(args.headings, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print("FAIL headings 文件不可读：%s（%s）" % (args.headings, e))
            return 2
        errs = _check_headings(doc, args.headings)
        if errs:
            for e in errs:
                print("FAIL", e)
            return 2
        hd, state = doc, "one"
    elif args.bid:
        hd, state, info = load_headings(args.bid)
    if state == "multi":
        print("FAIL bid 根存在多份 _headings_*.json，须人工确认后仅保留一份，或用 --headings 显式指定：")
        for f in info:
            print("  -", f)
        return 2
    if state == "bad":
        for m in info:
            print("FAIL", m)
        return 2
    p = os.path.join(args.bid, "01c_format-outline.json") if args.bid else args.out
    with open(p, "w", encoding="utf-8") as f:
        json.dump(build_01c(facts, headings=hd), f, ensure_ascii=False, indent=2)
    print("OK", p)
    if state == "one":
        print("章节树：_headings_*.json 真实派生（%d 条）；重跑 verify_format_chapters.py 保真核对"
              % len(hd["headings"]))
    else:
        print("⚠️ 章节树=FORMAT_CHAPTERS 冻结常量兜底（非本项目真实结构）；"
              "请人工抽取 bid 根 _headings_*.json（含 level）后重跑 ①")
    return 0


if __name__ == "__main__":
    sys.exit(main())
