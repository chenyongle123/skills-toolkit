#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 步 1：样式档生成（三档优先级）
================================================
按计划书 §8.1 三档优先级判定排版依据档位，生成 07_out/style-profile.yaml
与 07_out/排版依据说明.md：

  ① 招标明示（01c.typography.source == "tender_required"）：
     逐项取招标值（v0.25.0 起 ① 由 ⓪ blind_format 派生，值照录原文串）；
     **空值或不可解析＝【执行阻断】**（fail-loud，D4 修复：招标档关键项
     〔字体/字号/行距/页边距/页码〕缺陷＝上游 ① 抽取层缺口，不得静默代以
     基线）；sources 逐项记录。
     indent/binding/seal（套件扩展，⓪ 暗标 8 项之外）
     空值回落基线不阻断；page_limit 未载明（null）为合法态，仅提示铁律 3。
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
退出码：0＝已生成；2＝前置缺失或招标档关键项阻断（均零产物）。
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
    """'小四'/'12'/'12pt'/'四号字体' → pt；解析不出返回 None。

    同长度档位（'小四' vs '四号'）须"小X"系优先——'正文小四号'含'四号'
    子串，若'四号'先试会误判 14pt（正确为小四 12pt）。
    """
    if s is None:
        return None
    s = str(s).strip()
    for k in sorted(CN_SIZE_PT, key=lambda k: (len(k), k.startswith("小")), reverse=True):
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
    """'上2.5下2.5左3.2右3.2'/'上下2.54cm 左右3.17cm'/'上、下、左、右均为2.5cm' → dict；失败 None。"""
    if not s:
        return None
    t = (str(s).replace("：", ":").replace("，", ",").replace("、", "")
         .replace("厘米", "").replace("cm", "").replace("CM", "")
         .replace("Cm", "").replace("cM", "").replace(" ", ""))
    got = {}
    for side in ("top", "bottom", "left", "right"):
        cn = {"top": "上", "bottom": "下", "left": "左", "right": "右"}[side]
        m = re.search(cn + r":?(\d+(?:\.\d+)?)", t)
        if m:
            got[side] = round(float(m.group(1)), 2)
    if len(got) == 4:
        return got
    # 「上、下、左、右均为X」四边同值形态（、/均/cm 剥离后匹配）
    m = re.search(r"上下左右均?(?:为|是|:)?(\d+(?:\.\d+)?)", t)
    if m:
        v = round(float(m.group(1)), 2)
        return {"top": v, "bottom": v, "left": v, "right": v}
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
    """'页脚居中'/'页脚外侧'/'无'/'不得出现页码' → 规范值；解析不出 None。"""
    if s is None:
        return None
    t = str(s).replace(" ", "")
    # 负向表述优先判（不得出现页码/不设页码/不应出现页码/不得编页码/无页码…），
    # 须在页脚/页眉判断之前，防含「页脚」字样的禁页码表述被误判为页脚档
    if (re.search(r"不(得|应|设|能|要|用)?(出现|显示|设置|编制|编|印)?页码", t)
            or "无页码" in t or t in ("无", "不编页码")):
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

# D4 fail-loud：招标档（tender_required）以下关键排版项空值/不可解析＝执行阻断，
# 不静默代以基线（招标档缺项＝上游 ① 排版抽取层缺口）。
# 排除项：indent/binding/seal 为套件扩展项（⓪ 暗标 8 项之外），空值回落基线不阻断；
# page_limit schema 允许 null（招标未载明页数上限为合法态），仅提示铁律 3。
TENDER_FAIL_LOUD = ("font_body", "size_body_pt", "line_spacing", "margins_cm", "page_number")


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

    # 逐项取值：招标档→01c 值（关键项空值/不可解析＝执行阻断，D4）；
    # 模板档→模板解析（缺项回落基线）；基线档→基线。sources 记录逐项真实来源
    tpl = {}
    if tier == "client_template":
        if not template_path or not os.path.exists(template_path):
            print("【执行阻断】bid-docx-export（build_style_profile）未执行")
            print("原因：01c.typography.source=client_template 但未提供 --template（或文件不存在）")
            return 2
        tpl = parse_template_docx(template_path)

    warnings = []
    sources = {}
    missing_required = {}  # 招标档关键项 空值/不可解析 → 统一执行阻断（D4）

    def _block(key, why):
        missing_required.setdefault(key, why)

    def pick(key, tender_val, parsed_val, kind=str):
        """三档逐项取值：非空即用并记来源；空则回落基线——但招标档
        关键排版项（TENDER_FAIL_LOUD）空值＝执行阻断，不代以基线（D4）。"""
        if tier == "tender_required":
            if tender_val not in (None, "", []):
                return tender_val, "tender"
            if key in TENDER_FAIL_LOUD:
                _block(key, "空值（01c 未派生出该项——回 ① 检查 ⓪ blind_format 抽取）")
                return None, "tender"  # 占位：随后统一阻断，不落盘
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
    if tier == "tender_required":
        sources["font_body"] = "tender"  # 照录值恒 tender；空值已在 pick 阻断（不落盘）
    elif tier == "client_template" and tpl.get("font_body"):
        sources["font_body"] = "template"
    else:
        sources["font_body"] = "baseline"
    # size（招标档：空值或不可解析 → 阻断，不回落基线）
    sz_raw = typo.get("size_body")
    sz_t = parse_size(sz_raw)
    if tier == "tender_required" and sz_raw and sz_t is None:
        _block("size_body_pt", f"非空但无法解析（{sz_raw!r}）")
    sz_v, sz_src = pick("size_body_pt", sz_t, tpl.get("size_body_pt"))
    sources["size_body_pt"] = sz_src
    # spacing
    sp_raw = typo.get("line_spacing")
    sp_t = parse_spacing(sp_raw)
    if tier == "tender_required" and sp_raw and sp_t is None:
        _block("line_spacing", f"非空但无法解析（{sp_raw!r}）")
    sp_v, sp_src = pick("line_spacing", sp_t, tpl.get("line_spacing"))
    sources["line_spacing"] = sp_src
    # indent（套件扩展项：⓪ 暗标 8 项之外，空值回落基线不阻断）
    ind_t = parse_indent_chars(typo.get("indent"))
    ind_v, ind_src = pick("first_line_indent_chars", ind_t, tpl.get("first_line_indent_chars"))
    sources["first_line_indent_chars"] = ind_src
    # margins
    mg_raw = typo.get("margins")
    mg_t = parse_margins(mg_raw)
    if tier == "tender_required" and mg_raw and mg_t is None:
        _block("margins_cm", f"非空但无法解析（{mg_raw!r}）")
    mg_v, mg_src = pick("margins_cm", mg_t, tpl.get("margins_cm"))
    sources["margins_cm"] = mg_src
    # page_number
    pn_raw = typo.get("page_number")
    pn_t = parse_page_number(pn_raw)
    if tier == "tender_required" and pn_raw and pn_t is None:
        _block("page_number", f"非空但无法解析（{pn_raw!r}）")
    pn_v, pn_src = pick("page_number", pn_t, tpl.get("page_number"))
    sources["page_number"] = pn_src

    page_limit = typo.get("page_limit")
    if page_limit is not None:
        # 提取串内首个整数（'20'/'20页'/'不超过【20】页' → 20；铁律 1 值照录由原文承担）
        m = re.search(r"\d+", str(page_limit))
        if m:
            page_limit = int(m.group(0))
        else:
            warnings.append(f"page_limit 非数值（{page_limit!r}），按未载明处理")
            page_limit = None
    if tier == "tender_required" and page_limit is None:
        warnings.append("page_limit 未载明（null 为合法态，不阻断）——铁律 3："
                        "页数/字数偏差=重大扣分项，须人工复核招标文件确无页数上限")

    # 招标档关键项缺口：执行阻断（fail-loud，D4）——07_out 不落盘
    if missing_required:
        print("【执行阻断】bid-docx-export（build_style_profile）未执行")
        print("原因：01c.typography.source=tender_required（招标明示档），"
              "但以下关键排版项空值/不可解析：")
        for k in TENDER_FAIL_LOUD:
            if k in missing_required:
                print(f"      · {k}：{missing_required[k]}")
        print("处理：招标档缺项＝上游 ① 排版抽取层缺口，须回 ① 修复 01c 后重跑，"
              "不得静默代以基线（D4）")
        return 2

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
    }
    # style_source 一致性（§五：本次写回对齐；gate 再查 01c 与落盘值）
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
                  "招标文件对逐项参数的明示值照录（v0.25.0 起 ① 由 ⓪ blind_format 派生）。"
                  "关键排版项（字体/字号/行距/页边距/页码）空值或不可解析时生成即【执行阻断】，"
                  "不代以基线；下表「来源」列中的基线项仅为套件扩展项"
                  "（如首行缩进——⓪ 暗标 8 项之外）。")
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
        print(f"⚠️ {n_fallback} 项回落基线（招标档＝套件扩展项 indent；模板档＝模板未含该项；"
              f"关键项空值已在生成前阻断，详见排版依据说明.md）")
    for w in warnings:
        print("⚠️", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
