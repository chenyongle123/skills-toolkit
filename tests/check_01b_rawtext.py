# -*- coding: utf-8 -*-
"""P1-d 机检：01b raw_text 引文与招标原文逐行一致。

比对口径（归一化仅去 docx 提取噪声，不改内容）：
- 去所有空白；
- 中英标点等价（,＝， ;＝； :＝： !＝！ ?＝？ 等）；
- 引文按「……」切片，逐片须命中**任一**锚点段/表行文本（子串），且首尾
  须落在原文标点边界（防无省略号的静默截断/静默删句）；
  （「；Pxxxx重申」类次级锚点允许措辞差异，如 UNIX→LINUX、原文笔字，
  引文择其清洁一处照录，锚点注释两处都列。）
- 锚点取 raw_text 尾部括号内的全部 Pxxxx / TxRx 编号（兼容「（合同P1356）」
  「（前附表1.3.3，T1R10）」「（P3352；P3351同）」等记法）。
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

# 片段首尾允许的边界字符（命中任一锚点的归一化文本后判定）
BOUND = set("。，；：、）」』》”’！？.")
SENT_END = set("。！？")

def boundary_ok(frag_n, unit_n):
    """frag_n 须为 unit_n 子串；片段起点前须是标点/段首，片段终点后须是
    句终符/标点/段尾——防无省略号的静默截断与静默删句。"""
    i = unit_n.find(frag_n)
    if i < 0:
        return False
    before_ok = i == 0 or unit_n[i - 1] in BOUND
    j = i + len(frag_n)
    after_ok = j == len(unit_n) or frag_n[-1] in SENT_END or unit_n[j] in BOUND
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
            elif not any(boundary_ok(norm(frag), norm(units[a])) for a in anchors if a in units):
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
    units = {}
    for line in open(DUMP, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3 and re.match(r"^(P\d+|T\d+R\d+)$", parts[0]):
            units[parts[0]] = parts[-1]

    fails = check_items(units, psi.SPEC_ITEMS)
    n_quant = sum(1 for it in psi.SPEC_ITEMS[2:]
                  if re.search(r"[<>≥≤]", it["required_value"]) and it["unit"])
    print(f"条目总数 {len(psi.SPEC_ITEMS)}（第五章2.性能指标新增 {len(psi.SPEC_ITEMS)-2}，"
          f"其中带比较符可量化 {n_quant}）")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("PASS 全部 raw_text 引文与原文逐行一致")


if __name__ == "__main__":
    main()
