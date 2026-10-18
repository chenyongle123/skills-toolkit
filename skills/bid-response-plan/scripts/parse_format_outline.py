# -*- coding: utf-8 -*-
"""
parse_format_outline.py —— ① bid-response-plan 格式章抽取（01c）
计划书 §5 目录树 / 计划书 §6.2（01c_format-outline.json 契约）。

定位：01c 不是从招标原文**自动解析**得来的（本套件 ① 不读招标原文，
计划书 §3.2 边界）——章节树是**按本项目第七章「投标文件格式」人工逐字抽取
后固化**的常量；本脚本负责把它序列化为 01c 产物并做保真自检提示。

🔴 保真规则（v0.3.0 加固，验收记录 #2 实测缺陷）：编号与章节名**逐字照录**——
   ① 原文档编号不连续时（如技术标 1、2、7–12）**不得连续化重排**；
   ② 章节名中的括号说明（如「项目实施方案（由投标人自行编制）」）**不得删除**；
   ③ 换项目覆盖 FORMAT_CHAPTERS 常量后，必须跑
      scripts/verify_format_chapters.py 与抽取结果比对，全部逐字一致方可采用。

独立用法：python parse_format_outline.py --bid <项目>/bid [--out 01c_format-outline.json]
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- 01c 章节树（本项目第七章「投标文件格式」逐字） ----------
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

# 排版要求（前附表3.7.3/3.7.4/3.7.5 + 默认基线；未载明页限 → null）
TYPOGRAPHY = {
    "scope": "full_doc",
    "font_body": "", "size_body": "", "line_spacing": "",
    "margins": "", "page_number": "", "page_limit": None,
    "identity_ban": [],
    "indent": "首行缩进2字符（通用基线，招标未载明）",
    "binding": "A4幅胶装成册、不可拆卸；商务/技术/报价分开装订（前附表3.7.5）",
    "seal": "电子CA签章或纸质PDF扫描；纸质正本重要内容法人或授权代理人签字（前附表3.7.3）",
    "source": "tender_required",
}


def build_01c():
    """序列化 01c_format-outline.json（契约 0.2，assets/format-outline.schema.json）。"""
    return {
        "schema_version": "0.2",
        "chapters": [
            {"id": i, "number": n, "title": t, "level": lv, "page": "n/a-无分页"}
            for (i, n, t, lv) in FORMAT_CHAPTERS
        ],
        "typography": TYPOGRAPHY,
    }


def main():
    ap = argparse.ArgumentParser(description="生成 01c_format-outline.json（章节树常量→契约产物）")
    ap.add_argument("--bid", help="项目 bid 目录（与 --out 二选一）")
    ap.add_argument("--out", help="输出文件路径（与 --bid 二选一）")
    args = ap.parse_args()
    if not args.bid and not args.out:
        ap.error("必须指定 --bid 或 --out")
    p = os.path.join(args.bid, "01c_format-outline.json") if args.bid else args.out
    with open(p, "w", encoding="utf-8") as f:
        json.dump(build_01c(), f, ensure_ascii=False, indent=2)
    print("OK", p)
    print("⚠️ 若本项目重新覆盖过 FORMAT_CHAPTERS：必须跑 verify_format_chapters.py 与第七章原文逐字比对")


if __name__ == "__main__":
    main()
