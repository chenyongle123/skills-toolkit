#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 步 1：样式档生成（三档优先级）
================================================
按计划书 §8.1 三档优先级判定排版依据档位，生成 07_out/style-profile.yaml
与 07_out/排版依据说明.md：

  ① 招标明示（01c.typography.source == "tender_required"）：
     逐项取招标值；**空值项回落基线**并在 sources 逐项记录（示例市形态：
     source=tender_required 但 font_body/size_body/… 多为空串）。
  ② 甲方模板（source == "client_template"，须 --template <docx>）：
     纯标准库解析模板 docx 的 docDefaults/sectPr（零三方依赖），
     解析不到的项回落基线。
  ③ 通用中文基线（source == "baseline" 或 01c 无 typography）：
     整体套用 assets/style-profiles/通用中文基线.yaml。

暗标叠加层（assets/style-profiles/暗标叠加层.yaml）：与 bid_mode=blind 绑定，
正交叠加（overlay_blind=true），不是第四档、不参与档位判定。

只生成样式档与依据说明，不导出文档、不判定合规。
style_source 与 01c.typography.source 不一致 → 记 warning（export 时阻断）。

运行要求：Python ≥ 3.8（纯标准库）。用法：
  python build_style_profile.py --bid <项目/bid目录> [--template <甲方模板.docx>]
退出码：0＝已生成；2＝前置缺失（零产物）。
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
import zipfile

import _common as _C

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(SKILL_DIR, "assets", "style-profiles")

# 中文字号 → pt（GB/T 9704 常用档）
CN_SIZE_PT = {
    "初号": 42, "小初": 36, "一号": 26, "小一": 24, "二号": 22, "小二": 18,
    "三号": 16, "小三": 15, "四号": 14, "小四": 12, "五号": 10.5, "小五": 9,
    "六号": 7.5, "小六": 6.5,
}


def _load_baseline():
    """单一真值：assets/style-profiles/通用中文基线.yaml（F16b 消除硬编码双源）。

    类型归一到运行期口径（margins_cm 行内 dict → float dict；数值项 float），
    与原硬编码常量逐键同型。读不到/解析不出返回 None——main 入口阻断报缺件，
    不静默回落（双源漂移比缺件更危险）。
    """
    p = os.path.join(ASSETS, "通用中文基线.yaml")
    try:
        with open(p, encoding="utf-8") as f:
            raw = f.read()
        raw = "\n".join(re.sub(r"\s+#.*$", "", ln) for ln in raw.splitlines())  # 受控基线剥行尾注释
        t = _C.parse_style_yaml(raw)["typography"]
        out = {
            "font_body": str(t["font_body"]),
            "size_body_pt": float(t["size_body_pt"]),
            "line_spacing": float(t["line_spacing"]),
            "first_line_indent_chars": float(t["first_line_indent_chars"]),
            "page_number": str(t["page_number"]),
        }
        mg = str(t["margins_cm"]).strip("{}")
        out["margins_cm"] = {k.strip(): float(v)
                             for k, _, v in (kv.partition(":") for kv in mg.split(","))}
        if len(out["margins_cm"]) != 4:
            return None
        return out
    except (OSError, KeyError, ValueError, TypeError):
        return None


BASELINE = _load_baseline()

FONT_WHITELIST = re.compile(
    r"(仿宋|宋体|黑体|楷体|仿宋_GB2312|华文宋体|微软雅黑|等线|Times New Roman|Arial)", re.I)


def load_json(p):
    if not os.path.exists(p):
        print(f"【执行阻断】bid-docx-export（build_style_profile）未执行")
        print(f"原因：前置产物缺件：{p}")
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def parse_size(s):
    """'小四'/'12'/'12pt'/'四号字体' → pt；解析不出返回 None。"""
    if s is None:
        return None
    s = str(s).strip()
    for k in sorted(CN_SIZE_PT, key=len, reverse=True):
        if k in s:
            return float(CN_SIZE_PT[k])
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:pt|磅|P)?", s)
    if m:
        v = float(m.group(1))
        if 5 <= v <= 42:
            return v
    return None


def parse_spacing(s):
    """'1.5倍'/'固定值28磅'/'28磅' → 倍数（固定值按 /size 换算，size 缺省 12）。"""
    if s is None:
        return None
    s = str(s).strip()
    m = re.search(r"固定值|最小值", s)
    m_pt = re.search(r"(\d+(?:\.\d+)?)\s*磅", s)
    if m and m_pt:
        return round(float(m_pt.group(1)) / 12.0, 2)  # 与正文 12pt 换算等效倍数
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*倍", s)
    if m2:
        v = float(m2.group(1))
        if 1 <= v <= 3:
            return v
    m3 = re.match(r"^(\d+(?:\.\d+)?)$", s)
    if m3:
        v = float(m3.group(1))
        if 1 <= v <= 3:
            return v
    return None


def parse_margins(s):
    """'上2.5下2.5左3.2右3.2'/'上下2.54cm 左右3.17cm'/'2.54/3.17' → dict；失败 None。"""
    if not s:
        return None
    t = str(s).replace("：", ":").replace("，", ",").replace(" ", "")
    got = {}
    for side in ("top", "bottom", "left", "right"):
        cn = {"top": "上", "bottom": "下", "left": "左", "right": "右"}[side]
        m = re.search(cn + r":?(\d+(?:\.\d+)?)", t)
        if m:
            got[side] = round(float(m.group(1)), 2)
    if len(got) == 4:
        return got
    # 「上下X 左右Y」双值形态
    m = re.search(r"上下(\d+(?:\.\d+)?)左右(\d+(?:\.\d+)?)", t)
    if m:
        tb, lr = round(float(m.group(1)), 2), round(float(m.group(2)), 2)
        return {"top": tb, "bottom": tb, "left": lr, "right": lr}
    # 「X/Y」两值形态（上下/左右）
    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", t)
    if m:
        tb, lr = round(float(m.group(1)), 2), round(float(m.group(2)), 2)
        return {"top": tb, "bottom": tb, "left": lr, "right": lr}
    return None


def parse_page_number(s):
    """'页脚居中'/'页脚外侧'/'无' → 规范值；解析不出 None。"""
    if s is None:
        return None
    t = str(s).replace(" ", "")
    if "无页码" in t or t in ("无", "不编页码"):
        return "none"
    if "页脚" in t and ("外侧" in t or "奇偶" in t):
        return "footer_outer"
    if "页脚" in t or "下方" in t or "底部" in t:
        return "footer_center"
    if "页眉" in t or "上方" in t:
        return "header_center"
    return None


def parse_font(s):
    if not s:
        return None
    t = str(s).strip()
    if FONT_WHITELIST.fullmatch(t) or FONT_WHITELIST.search(t):
        return t.split()[0] if " " in t else t
    return None


def parse_indent_chars(s):
    """'首行缩进2字符（通用基线，招标未载明）' → 2；失败 None。"""
    if not s:
        return None
    m = re.search(r"缩进\s*(\d+(?:\.\d+)?)\s*字", str(s))
    if m:
        return float(m.group(1))
    return None


# ---------------- 甲方模板解析（纯标准库：zipfile + 正则，零三方依赖） ----------------

_TWIP_PER_CM = 567.0


def parse_template_docx(path):
    """解析甲方模板 docx 的 docDefaults/sectPr → 逐项样式 dict（缺项不补，交由回落）。"""
    out = {}
    try:
        with zipfile.ZipFile(path) as z:
            styles = z.read("word/styles.xml").decode("utf-8", "ignore")
            names = [n for n in z.namelist() if re.match(r"word/document\d*\.xml$", n)]
            doc = z.read("word/document.xml").decode("utf-8", "ignore") if names else ""
    except Exception as e:
        print(f"⚠️ 模板解析失败（{path}）：{e}；模板项将回落基线")
        return out
    dd = re.search(r"<w:docDefaults>.*?</w:docDefaults>", styles, re.S)
    seg = dd.group(0) if dd else styles
    m = re.search(r'<w:rFonts[^>]*w:eastAsia="([^"]+)"', seg)
    if m:
        out["font_body"] = m.group(1)
    m = re.search(r'<w:rFonts[^>]*w:ascii="([^"]+)"', seg)
    if m and not out.get("font_body"):
        out["font_body"] = m.group(1)
    m = re.search(r"<w:sz[^>]*w:val=\"(\d+)\"", seg)
    if m:
        out["size_body_pt"] = round(int(m.group(1)) / 2.0, 1)  # 半点 → pt
    m = re.search(r'<w:spacing[^>]*w:line="(\d+)"[^>]*w:lineRule="auto"', seg)
    if m:
        out["line_spacing"] = round(int(m.group(1)) / 240.0, 2)
    m = re.search(r'<w:ind[^>]*w:firstLineChars="(\d+)"', seg)
    if m:
        out["first_line_indent_chars"] = round(int(m.group(1)) / 100.0, 1)
    mg = re.search(r"<w:pgMar[^>]*/>", doc or styles)
    if mg:
        tag = mg.group(0)
        sides = {}
        for side, attr in (("top", "w:top"), ("bottom", "w:bottom"),
                           ("left", "w:left"), ("right", "w:right")):
            mm = re.search(attr + r'="(-?\d+)"', tag)
            if mm:
                sides[side] = round(int(mm.group(1)) / _TWIP_PER_CM, 2)
        if len(sides) == 4:
            out["margins_cm"] = sides
    return out


# ---------------- YAML 落盘（零依赖 mini dumper） ----------------

def _yaml_scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    if re.match(r"^-?\d+(?:\.\d+)?$", s) or s in ("true", "false", "null", "yes", "no", "on", "off"):
        return "'" + s + "'"  # 数字样/保留字文本必须引号，否则 YAML 读回变数字/布尔
    if re.match(r"^[\w.\u4e00-\u9fff/（）()、：:；;，,。\-—\s]+$", s) and not s.startswith(("-", "?")):
        return s
    return "'" + s.replace("'", "''") + "'"


def dump_yaml(data):
    lines = ["# ④ 导出链产物：样式档（由 build_style_profile.py 生成，勿手改）"]

    def emit(d, indent):
        for k, v in d.items():
            pad = " " * indent
            if isinstance(v, dict):
                lines.append(f"{pad}{k}:")
                emit(v, indent + 2)
            elif isinstance(v, list):
                if not v:
                    lines.append(f"{pad}{k}: []")
                else:
                    lines.append(f"{pad}{k}:")
                    for it in v:
                        lines.append(f"{pad}  - {_yaml_scalar(it)}")
            else:
                lines.append(f"{pad}{k}: {_yaml_scalar(v)}")

    emit(data, 0)
    return "\n".join(lines) + "\n"
# ---------------- 主逻辑 ----------------

TIER_LABEL = {
    "tender_required": "① 招标明示（01c.typography）",
    "client_template": "② 甲方模板（--template 解析）",
    "baseline": "③ 通用中文基线（内置）",
}


def build_profile(bid, template_path):
    meta = load_json(os.path.join(bid, "00_metadata.json"))
    if meta is None:
        return 2
    o1c = load_json(os.path.join(bid, "01c_format-outline.json"))
    if o1c is None:
        return 2
    typo = o1c.get("typography") or {}
    src = typo.get("source", "baseline") or "baseline"

    # 档位判定（§8.1 三档不得颠倒）
    if src == "tender_required":
        tier = "tender_required"
    elif src == "client_template":
        tier = "client_template"
    else:
        tier = "baseline"

    # 逐项取值：招标档→01c 值；模板档→模板解析；基线档→基线
    # 空值/解析失败一律回落基线，sources 记录逐项真实来源
    tpl = {}
    if tier == "client_template":
        if not template_path or not os.path.exists(template_path):
            print("【执行阻断】bid-docx-export（build_style_profile）未执行")
            print("原因：01c.typography.source=client_template 但未提供 --template（或文件不存在）")
            return 2
        tpl = parse_template_docx(template_path)

    warnings = []
    sources = {}

    def pick(key, tender_val, parsed_val, kind=str):
        """三档逐项取值：非空即用并记来源；空则回落基线。返回 (值, 来源)。"""
        if tier == "tender_required":
            if tender_val not in (None, "", []):
                return tender_val, "tender"
            return BASELINE[key], "baseline"
        if tier == "client_template":
            if parsed_val is not None:
                return parsed_val, "template"
            return BASELINE[key], "baseline"
        return BASELINE[key], "baseline"

    # font
    font_raw = typo.get("font_body", "")
    if tier == "tender_required" and font_raw:
        font = font_raw  # 招标原文照录（铁律 1：不替招标改字）
        if not parse_font(font_raw):
            warnings.append(f"font_body「{font_raw}」不在常用字体白名单（仿宋/宋体/黑体/楷体/"
                            "Times New Roman 等）——照录但须人工确认投标环境可渲染，必要时澄清")
    else:
        font, _s = pick("font_body", font_raw, tpl.get("font_body"))
    sources["font_body"] = "tender" if (tier == "tender_required" and font_raw) else (
        "template" if (tier == "client_template" and tpl.get("font_body")) else "baseline")
    # size
    sz_t = parse_size(typo.get("size_body"))
    sz_v, sz_src = pick("size_body_pt", sz_t, tpl.get("size_body_pt"))
    if tier == "tender_required" and typo.get("size_body") and sz_t is None:
        warnings.append(f"size_body 无法解析（{typo.get('size_body')!r}），回落基线小四 12pt")
        sz_src = "baseline"
    sources["size_body_pt"] = sz_src
    # spacing
    sp_t = parse_spacing(typo.get("line_spacing"))
    sp_v, sp_src = pick("line_spacing", sp_t, tpl.get("line_spacing"))
    if tier == "tender_required" and typo.get("line_spacing") and sp_t is None:
        warnings.append(f"line_spacing 无法解析（{typo.get('line_spacing')!r}），回落基线 1.5 倍")
        sp_src = "baseline"
    sources["line_spacing"] = sp_src
    # indent
    ind_t = parse_indent_chars(typo.get("indent"))
    ind_v, ind_src = pick("first_line_indent_chars", ind_t, tpl.get("first_line_indent_chars"))
    sources["first_line_indent_chars"] = ind_src
    # margins
    mg_t = parse_margins(typo.get("margins"))
    mg_v, mg_src = pick("margins_cm", mg_t, tpl.get("margins_cm"))
    if tier == "tender_required" and typo.get("margins") and mg_t is None:
        warnings.append(f"margins 无法解析（{typo.get('margins')!r}），回落基线 2.54/3.17cm")
        mg_src = "baseline"
    sources["margins_cm"] = mg_src
    # page_number
    pn_t = parse_page_number(typo.get("page_number"))
    pn_v, pn_src = pick("page_number", pn_t, tpl.get("page_number"))
    sources["page_number"] = pn_src

    page_limit = typo.get("page_limit")
    if page_limit is not None:
        try:
            page_limit = int(page_limit)
        except (TypeError, ValueError):
            warnings.append(f"page_limit 非数值（{page_limit!r}），按未载明处理")
            page_limit = None

    profile = {
        "schema_version": "0.1",
        "tier": tier,
        "bid_mode": meta.get("bid_mode", "normal") or "normal",
        "overlay_blind": (meta.get("bid_mode") == "blind"),
        "generated_at": _dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "typography": {
            "font_body": font,
            "size_body_pt": sz_v,
            "line_spacing": sp_v,
            "first_line_indent_chars": ind_v,
            "margins_cm": mg_v,
            "page_number": pn_v,
            "page_limit": page_limit,
            "identity_ban": typo.get("identity_ban") or [],
            "binding": typo.get("binding", "") or "",
            "seal": typo.get("seal", "") or "",
            "indent_note": typo.get("indent", "") or "",
        },
        "sources": sources,
        "notes": [f"档位：{TIER_LABEL[tier]}"],
    }    # style_source 一致性（§五：本次写回对齐；gate 再查 01c 与落盘值）
    meta_ss = meta.get("style_source")
    if meta_ss and meta_ss != src:
        warnings.append(
            f"style_source 不一致：00_metadata.style_source={meta_ss} ≠ 01c.typography.source={src}"
            "（本次运行已写回对齐；若 01c 事后换档，须重跑本脚本，否则 export 阻断）")
    return profile, warnings, meta, tier, typo


PARAM_LABEL = {
    "font_body": "正文字体",
    "size_body_pt": "正文字号(pt)",
    "line_spacing": "行距(倍)",
    "first_line_indent_chars": "首行缩进(字符)",
    "margins_cm": "页边距(cm 上下/左右)",
    "page_number": "页码",
}
SRC_LABEL = {"tender": "招标明示", "template": "甲方模板", "baseline": "通用基线"}


def render_explanation(profile, warnings, meta, tier, typo):
    t = profile["typography"]
    mg = t["margins_cm"]
    md = []
    md.append("# 排版依据说明")
    md.append("")
    md.append(f"> 生成：bid-docx-export build_style_profile；"
              f"时间：{_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append("")
    md.append("## 一、采用档位")
    md.append("")
    if tier == "tender_required":
        md.append("**招标明示档**（01c.typography.source=tender_required）。"
                  "招标文件对逐项参数的明示值照录；**未载明的项回落通用中文基线**，"
                  "下表「来源」列逐项标注。")
    elif tier == "client_template":
        md.append("**甲方模板档**（01c.typography.source=client_template，--template 解析）。"
                   "模板可解析项照录；解析不到的项回落通用中文基线。")
    else:
        md.append("**无招标要求，采用基线**（01c.typography.source=baseline 或无 typography）。"
                  "整体套用通用中文基线。")
    md.append("")
    md.append("## 二、逐项参数与来源")
    md.append("")
    md.append("| 项 | 采用值 | 来源 |")
    md.append("|---|---|---|")
    srcs = profile["sources"]
    md.append(f"| 正文字体 | {t['font_body']} | {SRC_LABEL[srcs['font_body']]} |")
    md.append(f"| 正文字号 | {t['size_body_pt']} pt | {SRC_LABEL[srcs['size_body_pt']]} |")
    md.append(f"| 行距 | {t['line_spacing']} 倍 | {SRC_LABEL[srcs['line_spacing']]} |")
    md.append(f"| 首行缩进 | {t['first_line_indent_chars']} 字符 | {SRC_LABEL[srcs['first_line_indent_chars']]} |")
    md.append(f"| 页边距 | 上下 {mg['top']}/{mg['bottom']}，左右 {mg['left']}/{mg['right']} | {SRC_LABEL[srcs['margins_cm']]} |")
    md.append(f"| 页码 | {t['page_number']} | {SRC_LABEL[srcs['page_number']]} |")
    pl = t["page_limit"]
    md.append(f"| 页数上限 | {pl if pl else '未载明'} | "
              f"{'招标明示' if pl else '未载明——铁律 3：按招标隐含要求估算并写明依据'} |")
    md.append("")
    if tier == "tender_required":
        raw = {k: typo.get(k, "") for k in
               ("font_body", "size_body", "line_spacing", "margins", "page_number", "indent")}
        md.append("招标原始记载（01c.typography 逐字）：")
        md.append("```json")
        md.append(json.dumps(raw, ensure_ascii=False, indent=1))
        md.append("```")
        md.append("")
    if t["binding"]:
        md.append(f"**装订要求（招标）**：{t['binding']}")
    if t["seal"]:
        md.append(f"**签章要求（招标）**：{t['seal']}")
    md.append("")
    md.append("## 三、暗标叠加")
    md.append("")
    if profile["overlay_blind"]:
        md.append("bid_mode=blind：暗标叠加层生效（非第四档）——无页眉页脚单位名/无 LOGO/"
                  "文档属性作者类字段清空/正文不得出现投标人名称与人员姓名（verify 扫描报事实态）。")
    else:
        md.append("bid_mode=normal：普通标。元数据作者类字段照清（§8.6.3 两种标都清）；"
                  "页眉页脚单位名保留。")
    md.append("")
    # metadata.warnings 一并列出（00_metadata.schema：④ 在排版依据说明中一并列出）
    meta_warn = meta.get("warnings") or []
    if warnings or meta_warn:
        md.append("## 四、随档警告（含 00_metadata.warnings）")
        md.append("")
        for w in warnings:
            md.append(f"- ⚠️ {w}")
        for w in meta_warn:
            md.append(f"- ⓪①② 警告：[{w.get('code')}] {w.get('message')}")
        md.append("")
    md.append("## 五、基线定义")
    md.append("")
    md.append("通用中文基线：仿宋_GB2312／正文小四 12pt／1.5 倍行距／首行缩进 2 字符／"
              "页边距上下 2.54cm 左右 3.17cm／页码页脚居中（允许整份替换，不进判定逻辑）。")
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True)
    ap.add_argument("--template", default=None)
    args = ap.parse_args()
    bid = args.bid
    if not os.path.isdir(bid):
        print(f"【执行阻断】bid 目录不存在：{bid}")
        return 2
    if not BASELINE:
        print("【执行阻断】bid-docx-export（build_style_profile）未执行")
        print(f"原因：assets/style-profiles/通用中文基线.yaml 缺失或不可解析"
              f"（基线单一真值，缺失即阻断，不回落硬编码——F16b）")
        return 2
    res = build_profile(bid, args.template)
    if res == 2:
        return 2
    profile, warnings, meta, tier, typo = res
    src = typo.get("source", "baseline") or "baseline"

    out_dir = os.path.join(bid, "07_out")
    os.makedirs(out_dir, exist_ok=True)
    yml = dump_yaml(profile)
    with open(os.path.join(out_dir, "style-profile.yaml"), "w", encoding="utf-8") as f:
        f.write(yml)
    expl = render_explanation(profile, warnings, meta, tier, typo)
    with open(os.path.join(out_dir, "排版依据说明.md"), "w", encoding="utf-8") as f:
        f.write(expl)

    # style_source 写回 00_metadata（gate 一致性检查的闭环锚点：与 01c.typography.source 对齐）
    meta_p = os.path.join(bid, "00_metadata.json")
    try:
        with open(meta_p, encoding="utf-8") as f:
            cur = json.load(f)
        if cur.get("style_source") != src:
            cur["style_source"] = src
            cur["updated_at"] = _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
            with open(meta_p, "w", encoding="utf-8") as f:
                json.dump(cur, f, ensure_ascii=False, indent=1)
    except (OSError, json.JSONDecodeError):
        print("⚠️ 00_metadata.json 不可写/不可解析：style_source 未能写回（gate 将告警）")

    t = profile["typography"]
    print("样式档已生成：07_out/style-profile.yaml + 排版依据说明.md")
    print(f"档位：{TIER_LABEL[tier]}；正文 {t['font_body']} {t['size_body_pt']}pt / "
          f"{t['line_spacing']} 倍行距 / 缩进 {t['first_line_indent_chars']} 字符")
    n_fallback = sum(1 for v in profile["sources"].values() if v == "baseline")
    if tier != "baseline" and n_fallback:
        print(f"⚠️ {n_fallback} 项招标/模板未载明，回落基线（详见排版依据说明.md）")
    for w in warnings:
        print("⚠️", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
