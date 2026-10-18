# -*- coding: utf-8 -*-
"""P1-d 机检：01b raw_text 引文与招标原文逐行一致。

比对口径（归一化仅去 docx 提取噪声，不改内容）：
- 去所有空白；
- 中英标点等价（,＝， ;＝； :＝： !＝！ ?＝？ 等）；
- 引文按「……」切片，逐片须命中**任一**锚点段/表行文本（子串，忽略制表符），且首尾
  须落在原文边界（段首/段尾/标点/句终符；T 行另有单元格边界，见下）——
  防无省略号的静默截断/静默删句；
  （「；Pxxxx重申」类次级锚点允许措辞差异，如 UNIX→LINUX、原文笔字，
  引文择其清洁一处照录，锚点注释两处都列。）
- 锚点取 raw_text 尾部括号内的全部 Pxxxx / TxRx 编号（兼容「（合同P1356）」
  「（前附表1.3.3，T1R10）」「（P3352；P3351同）」等记法）。

单元文本提取（load_units）：
- P 行 `Pxxxx<TAB>样式<TAB>正文` 取正文（正文含制表符时拼接样式之后全部字段）；
- T 行 `TxRy<TAB>单元格…` 拼接**全部单元格**——数据在非末列且末列为空的
  表格行（如示例市 T39 图纸资料分配表）此前整行不可见，v0.5.1 修复。
  制表符保留在单元文本中作为**单元格边界**参与首尾边界判定：片段可跨
  单元格（如「1、施工图图纸6套」跨名称/数量两格），但起止须落在单元格
  边界或标点/段首段尾——既补缺口，又防跨单元格蒙混（v0.5.2 定型）。
"""
import json, re, sys, importlib.util

DUMP = r"<受控项目根>\示例发包人示例市100MW风电EPC\src\full_dump.txt"
PSI = r"<仓库根>\skills\bid-response-plan\scripts\parse_spec_items.py"
if "--psi" in sys.argv:
    PSI = sys.argv[sys.argv.index("--psi") + 1]

PUNCT = str.maketrans({",": "，", ";": "；", ":": "：", "!": "！", "?": "？",
                       "(": "（", ")": "）"})


def norm(s):
    return re.sub(r"\s+", "", s).translate(PUNCT)


def load_units(path):
    """段号/行号 -> 原文文本（见模块 docstring 单元文本提取规则）。"""
    units = {}
    for line in open(path, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2 and re.match(r"^P\d+$", parts[0]):
            units[parts[0]] = "\t".join(parts[2:]) if len(parts) > 3 else parts[-1]
        elif len(parts) >= 2 and re.match(r"^T\d+R\d+$", parts[0]):
            units[parts[0]] = "\t".join(parts[1:])
    return units

# 片段首尾允许的边界字符（命中任一锚点的归一化文本后判定）
BOUND = set("。，；：、）」』》”’！？.")
SENT_END = set("。！？")

def boundary_ok(frag_n, unit_raw):
    """frag_n（归一化片段）须为 unit（忽略制表符）子串；片段起点前须是
    标点/单元格边界/段首，终点后须是句终符/标点/单元格边界/段尾——
    防无省略号的静默截断与静默删句。unit_raw 保留制表符（T 行=单元格
    边界）：片段可跨单元格，但起止须落在单元格边界或标点，防跨单元格蒙混。"""
    flat, idx_map = [], []
    for k, ch in enumerate(unit_raw):
        if ch.isspace():
            continue
        flat.append(ch)
        idx_map.append(k)
    # 与 norm() 同等归一化（去空白＋中英标点等价；maketrans 为逐字符映射，位置不变）
    flat = "".join(flat).translate(PUNCT)
    i = flat.find(frag_n)
    if i < 0:
        return False
    before_ok = i == 0 or flat[i - 1] in BOUND or unit_raw[idx_map[i] - 1] == "\t"
    j = i + len(frag_n)
    after_ok = (j == len(flat) or frag_n[-1] in SENT_END or flat[j] in BOUND
                or unit_raw[idx_map[j] - 1] == "\t")
    return before_ok and after_ok

def check_items(units, items):
    """对给定 items 跑全部机检，返回失败信息列表（空=通过）。

    units：段号/行号 -> 原文文本；items：01b 条目（含 raw_text）。
    逻辑与主程序共用，供 test_stage1_regression.py 的 R4 以合成数据回归。
    """
    fails = []
    for it in items:
        rt = it["raw_text"]
        m = re.search(r"（([^（）]*\d[^（）]*)）\s*$", rt)
        if not m:
            fails.append(f"{it['id']}: raw_text 无尾部锚点注释")
            continue
        anchors = re.findall(r"P\d+|T\d+R\d+", m.group(1))
        if not anchors:
            fails.append(f"{it['id']}: 尾部注释无段号/行号")
            continue
        quote = rt[: m.start()]
        frags = [f for f in re.split(r"…+", quote) if f.strip()]
        if not frags:
            fails.append(f"{it['id']}: 引文为空")
            continue
        for a in anchors:
            if a not in units:
                fails.append(f"{it['id']}: 锚点 {a} 不存在于原文")
        for frag in frags:
            if not any(norm(frag) in norm(units[a]) for a in anchors if a in units):
                fails.append(f"{it['id']}: 片段不在任何锚点 {anchors} 原文中 → {frag[:36]}…")
            elif not any(boundary_ok(norm(frag), units[a]) for a in anchors if a in units):
                fails.append(f"{it['id']}: 片段首尾未落在原文边界（疑无省略号截断/删句）→ {frag[:36]}…")
    # 附加机检：id 唯一且合模式、schema 必填字段非空
    ids = [it["id"] for it in items]
    if len(set(ids)) != len(ids):
        fails.append("id 重复")
    for it in items:
        for k in ("clause", "page", "requirement", "required_value", "raw_text"):
            if not str(it.get(k, "")).strip():
                fails.append(f"{it['id']}: 字段 {k} 为空")
        if not re.match(r"^sp-\d{3,}$", it["id"]):
            fails.append(f"{it['id']}: id 不合模式")
    return fails


def main():
    spec = importlib.util.spec_from_file_location("psi", PSI)
    psi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(psi)

    # 段号/行号 -> 文本
    units = load_units(DUMP)

    fails = check_items(units, psi.SPEC_ITEMS)
    n_ch5 = sum(1 for it in psi.SPEC_ITEMS if it["clause"].startswith("第五章"))
    n_quant = sum(1 for it in psi.SPEC_ITEMS[2:]
                  if re.search(r"[<>≥≤]", it["required_value"]) and it["unit"])
    print(f"条目总数 {len(psi.SPEC_ITEMS)}（第五章已全量 {n_ch5} 行：2.性能指标14＋3.勘察设计69"
          f"＋5.调试验收5＋6.施工工期16＋8.竣工试验与验收131；挂起 1/4/7/9 节，"
          f"其中带比较符可量化 {n_quant}）")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("PASS 全部 raw_text 引文与原文逐行一致")


if __name__ == "__main__":
    main()
