# -*- coding: utf-8 -*-
"""
parse_business_forms.py —— ① bid-response-plan 商务表格框架抽取（03c）
计划书 §5 目录树 / 计划书 §6.2（03c_business-forms.json 契约）/ M8（check_business 依据）。

定位：03c 是招标「投标文件格式」章商务表格的**框架抽取**——只记结构与位置
（表名/必填字段/签章/份数），**不含任何金额**；金额由人填好后回填
filled_file。② 的 D 类/M8 检查以本产物为唯一依据。

独立用法：python parse_business_forms.py --bid <项目>/bid [--out 03c_business-forms.json]
"""
import argparse, difflib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_format_outline import (  # 章节锚定（单一真源，不复制）
    chapter_context_titles_list, chapter_id_exact)

# 03c 商务表格框架
# (id, name, chapter_title, required_fields, seal, copies)
BUSINESS_FORMS = [
    ("bf-01","投标函","投标函格式",["投标总报价（大写）","投标总报价（小写）","安全文明施工费","危大工程施工技术措施费","开工日期","全部机组并网发电日期","移交生产完成日期","竣工验收完成日期","投标有效期承诺"],"法定代表人签字+单位公章",5),
    ("bf-02","投标保证金","投标保证金格式",["保证金金额（大写）","保证金金额（小写）","账号","保函/转账凭证"],"按前附表3.4.1",5),
    ("bf-03","法定代表人身份证明","法定代表人身份证明",["姓名","性别","年龄","职务","系（投标人）的法定代表人"],"附身份证复印件",5),
    ("bf-04","授权委托书","授权委托书",["委托人","受托人","授权范围","授权期限"],"法人签字+单位公章",5),
    ("bf-05","商务偏差声明函","商务偏差声明函",["条款号","招标文件要求","偏差内容","说明理由"],"按前附表3.7.3",5),
    ("bf-06","投标人基本情况表","投标人基本情况表",["名称","注册地址","成立时间","注册资本","法定代表人","联系方式"],"单位公章",5),
    ("bf-07","财务及资信状况","财务及资信状况",["近三年审计报告","银行资信证明","信用查询截图（4项）"],"单位公章",5),
    ("bf-08","投标人资格声明格式","投标人资格声明格式",["资质等级","证书编号","有效期"],"单位公章",5),
    ("bf-09","制造商的资格声明格式","制造商的资格声明格式",["制造商名称","货物名称","资质"],"制造商盖章",5),
    ("bf-10","已完工的业绩表","已完工的业绩表",["项目名称","发包人","合同金额","竣工日期","项目经理"],"单位公章+证明",5),
    ("bf-11","正在实施的和新承接的项目情况表","正在实施的和新承接的项目情况表",["项目名称","发包人","合同金额","进度"],"单位公章",5),
    ("bf-12","施工分包情况表","施工分包情况表（适用于投标人不具备招标文件所要求的施工资质的情况）",["分包内容","分包人","资质"],"单位公章",5),
    ("bf-13","设计分包情况表","设计分包情况表（适用于投标人不具备招标文件所要求的设计资质的情况）",["分包内容","分包人","资质"],"单位公章",5),
    ("bf-14","主要设备、材料备选供应商名单","主要设备、材料备选供应商名单",["设备/材料名称","备选供应商"],"单位公章",5),
    ("bf-15","备品备件情况一览表","备品备件情况一览表",["名称","规格","数量"],"单位公章",5),
    ("bf-16","专用工具情况一览表","专用工具情况一览表",["名称","规格","数量"],"单位公章",5),
    ("bf-17","进口设备/部件情况一览表","进口设备/部件情况一览表",["名称","产地","数量"],"单位公章",5),
    ("bf-18","外购设备/部件情况一览表","外购设备/部件情况一览表",["名称","供应商","数量"],"单位公章",5),
    ("bf-19","技术偏差声明函","技术偏差声明函",["条款号","招标文件要求","偏差内容","说明理由"],"按前附表3.7.3",5),
    ("bf-20","报价汇总表","报价汇总表",["子目名称","单价","合价","投标总价"],"法定代表人签字+单位公章",5),
    ("bf-21","施工辅助工程报价表","施工辅助工程报价表",["子目名称","单价","合价"],"按报价要求1.1-1.17",5),
    ("bf-22","设备及安装工程报价表","设备及安装工程报价表",["子目名称","单价","合价"],"按报价要求",5),
    ("bf-23","建筑工程费用报价表","建筑工程费用报价表",["子目名称","单价","合价"],"按报价要求",5),
    ("bf-24","其他费用报价表","其他费用报价表",["子目名称","单价","合价"],"按报价要求",5),
]


def resolve_form_chapter(fid, name, chap):
    """商务表→当前 01c 章节树 chapter_id（逐字两跳，不做槽推导）。

    第一跳 chapter_title（模板树自洽口径：模板表头绑定模板格式章名）；
    第二跳表名（派生树常见口径：真实格式章多为「一~九」平铺，章题即表名，
    如「投标函」）。两跳皆空 → None（调用方 fail-loud——商务表挂接错章
    比报错更糟，不猜语义槽）。
    """
    cid = chapter_id_exact(chap)
    if cid is None:
        cid = chapter_id_exact(name)
    return cid


def validate_forms_chapter_linkage(forms=None):
    """商务表→01c 章节挂接校验（显式、fail-loud，不自动补猜）。

    - 表须逐字命中当前 01c 章节树（章节标题→表名两跳，见
      resolve_form_chapter）；失配 → 报错退出并给近邻候选
      （裸 None/静默挂错章均不可接受）；
    - 一章一表：同一章节被两张商务表绑定 → 报错退出（挂接错位）。
    build_03c 与 build_task_cards.build_03（03c 镜像块）共用户校验；
    章节树随锚定上下文走（链内=派生树，独立用法=常量兜底树）。
    """
    seen = {}
    for (fid, name, chap, _rf, _seal, _copies) in (forms if forms is not None else BUSINESS_FORMS):
        cid = resolve_form_chapter(fid, name, chap)
        if cid is None:
            titles = chapter_context_titles_list()
            near = (difflib.get_close_matches(chap, titles, n=3, cutoff=0.6)
                    or difflib.get_close_matches(name, titles, n=3, cutoff=0.6))
            hint = ("相近候选：" + " / ".join(near)) if near else "无相近候选"
            sys.exit("[parse_business_forms] 表 %s「%s」章节标题 %r 与表名均未逐字命中当前 01c 章节树；%s。"
                     "模板口径见 parse_format_outline.FORMAT_CHAPTERS；本项目无此表时须人工裁剪/改写 BUSINESS_FORMS"
                     "（派生树来自 bid 目录 _headings_*.json 抽取，章题以抽取为准）"
                     % (fid, name, chap, hint))
        if cid in seen:
            sys.exit("[parse_business_forms] 章节 %s 同时绑定表 %s「%s」与表 %s「%s」——一章一表，请修正挂接"
                     % (cid, seen[cid][0], seen[cid][1], fid, name))
        seen[cid] = (fid, name)


def build_03c():
    """序列化 03c_business-forms.json（契约 0.1，assets/business-forms.schema.json）。"""
    validate_forms_chapter_linkage()
    forms = []
    for (fid, name, chap, rf, seal, copies) in BUSINESS_FORMS:
        forms.append({
            "id": fid, "name": name, "tender_page": "n/a-无分页",
            "chapter_id": resolve_form_chapter(fid, name, chap),
            "required_fields": rf, "seal": seal,
            "copies": copies, "filled_file": "", "status": "blank",
        })
    return {
        "schema_version": "0.1",
        "forms": forms,
        "consistency_rules": [
            "大写金额 = 小写金额",
            "各报价表分项合计 = 报价汇总表投标总价",
            "投标保证金金额与招标文件前附表3.4.1载明一致",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="生成 03c_business-forms.json（商务表框架）")
    ap.add_argument("--bid", help="项目 bid 目录（与 --out 二选一）")
    ap.add_argument("--out", help="输出文件路径（与 --bid 二选一）")
    args = ap.parse_args()
    if not args.bid and not args.out:
        ap.error("必须指定 --bid 或 --out")
    p = os.path.join(args.bid, "03c_business-forms.json") if args.bid else args.out
    with open(p, "w", encoding="utf-8") as f:
        json.dump(build_03c(), f, ensure_ascii=False, indent=2)
    print("OK", p, "（%d 表，无金额）" % len(BUSINESS_FORMS))


if __name__ == "__main__":
    main()
