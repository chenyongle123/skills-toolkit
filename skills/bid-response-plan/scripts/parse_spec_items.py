# -*- coding: utf-8 -*-
"""
parse_spec_items.py —— ① bid-response-plan 技术规范条目抽取（01b）
计划书 §5 目录树 / 计划书 §6.2（01b_spec-items.json 契约）。

定位：01b 是**按接缝例外**从招标技术规范表**逐行抄录**的产物（条款号/原文/
要求值/单位/公差），**不得判定是否废标、是否偏离、风险等级**（抄行可核对，
判定不可核对）。行数须与规范表逐行一致：合并单元格拆多行、跨页同表连续
计数不重置、并列项计多项。**散文章节**（无表格的性能指标一类）按「每个
可独立核验（通过/不通过）的要求一行」拆分，并列保证值（全场/单台、
日间/夜间）计多行——示例市项目 2.性能指标节按此口径拆 14 行（sp-003–
sp-016），其中可量化 8 行，覆盖阶段 1 验收记录 §#1 所列 7 条可量化基准
（另收强迫停机率 1 条）及 6 条定性行（主机考核/GB-DL/国产化/等保/
智慧电站/调度数据网）。

🔴 覆盖状态（v0.16 阶段 1 验收 #1 → P1-d 已部分解除，**未全量**）：
- 已全量：第五章「发包人要求」2.性能指标（P3333–P3353，14 行）；
- 挂起：第五章其余 8 节（1.总则／3.勘察设计／4.施工安装／5.风电场调试、
  试运行和验收／6.施工工期／7.施工质量／8.竣工试验与验收／9.工程管理）
  及其它章节技术规范——**不得用现有行数冒充第五章全覆盖**；
- sp-001/sp-002 为合同条款/前附表来源（不在第五章技术规范表内，验收记录
  #1 已注明该口径下覆盖率实质为 0），保留作跨章节技术要求，clause 已精确
  到条款号。

独立用法：python parse_spec_items.py --bid <项目>/bid [--out 01b_spec-items.json]
"""
import argparse, json, os

# 技术规范条目。源：示例发包人示例市 100MW 风电 EPC 招标文件 docx（无稳定页码，
# page 统一填 n/a-无分页，raw_text 尾部（Pxxxx）为段号锚点，供逐行核对）。
SPEC_ITEMS = [
    # —— 跨章节技术要求（合同条款/前附表来源，非第五章技术规范表内）——
    {"id": "sp-001", "clause": "通用合同条款9.1.5", "page": "n/a-无分页",
     "requirement": "试运行考核周期", "required_value": "240", "unit": "小时",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "试运行考核周期：240小时。（合同P1356）"},
    {"id": "sp-002", "clause": "前附表1.3.3", "page": "n/a-无分页",
     "requirement": "一次验收合格率", "required_value": "100%", "unit": "%",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "工程质量符合国家、行业现行有关设计、施工、验收规范标准，一次验收合格率100%。（前附表1.3.3，T1R10）"},
    # —— 第五章「发包人要求」2.性能指标（P3333–P3353，全量 14 行）——
    # 1）风电机组 →（1）可靠性保证
    {"id": "sp-003", "clause": "第五章2.性能指标1）（1）", "page": "n/a-无分页",
     "requirement": "全场风电机组可利用率", "required_value": "≥98%", "unit": "%",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "本工程可利用率取全部机组缺陷责任期满（包括缺陷责任期的延长）时的平均值作为[考核可利用率]。最终验收的条件，全场风电机组可利用率不少于98%……（P3337）"},
    {"id": "sp-004", "clause": "第五章2.性能指标1）（1）", "page": "n/a-无分页",
     "requirement": "单台风机可利用率", "required_value": "≥96%", "unit": "%",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "……单台风机的可利用率达到96%及以上，风场所有风机正常运行。（P3337）"},
    # 1）风电机组 →（2）功率曲线保证
    {"id": "sp-005", "clause": "第五章2.性能指标1）（2）", "page": "n/a-无分页",
     "requirement": "功率曲线保证值", "required_value": "≥97%", "unit": "%",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "在缺陷责任期内，承包人对功率曲线的保证值应大于或等于保证功率曲线为基础计算出的风机发电量的97%……（P3339）"},
    {"id": "sp-006", "clause": "第五章2.性能指标1）（2）", "page": "n/a-无分页",
     "requirement": "单机功率曲线保证值", "required_value": "≥95%", "unit": "%",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "……单台风机的功率曲线的保证值达到95%。（P3339）"},
    # 1）风电机组 →（3）噪声保证
    {"id": "sp-007", "clause": "第五章2.性能指标1）（3）", "page": "n/a-无分页",
     "requirement": "噪声（距风机300米）日间", "required_value": "≤55", "unit": "dB",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "风机运行时距离风机300米测量的噪音水平日间不大于55dB……（P3341）"},
    {"id": "sp-008", "clause": "第五章2.性能指标1）（3）", "page": "n/a-无分页",
     "requirement": "噪声（距风机300米）夜间", "required_value": "≤45", "unit": "dB",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "……夜间不大于45dB，在对噪声有要求和限制的区域，机组排放的噪声应符合该区域所执行的相关标准的规定。（P3341）"},
    # 1）风电机组 →（4）主机考核标准
    {"id": "sp-009", "clause": "第五章2.性能指标1）（4）", "page": "n/a-无分页",
     "requirement": "主机考核标准", "required_value": "经过检验测试合格，完全符合合同的要求", "unit": "",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "承包商保证所提供的合同设备经过检验测试合格，完全符合合同的要求。（P3343）"},
    # 2）场内集电线路、升压站等公用系统设备性能考核
    {"id": "sp-010", "clause": "第五章2.性能指标2）", "page": "n/a-无分页",
     "requirement": "公用系统设备性能（集电线路、升压站）",
     "required_value": "不低于中国国家标准（GB系列）或电力行业标准（DL系列）的相关规定（执行较高标准）", "unit": "",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "承包商提供的场内集电线路、升压站等公用系统设备性能指标不低于中国国家标准（GB系列）或电力行业标准（DL系列）的相关规定（执行较高标准）……（P3346）"},
    {"id": "sp-011", "clause": "第五章2.性能指标2）", "page": "n/a-无分页",
     "requirement": "公用系统设备质量原因致风机强迫停机率（平均每台）",
     "required_value": "<5%", "unit": "%",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "承包人保证因由上述承包商提供的公用系统设备质量原因造成的风电机组强迫停机率平均每台风电机组应少于5%。（P3346）"},
    # 3）产能保证指标
    {"id": "sp-012", "clause": "第五章2.性能指标3）", "page": "n/a-无分页",
     "requirement": "年等效满负荷运行小时数", "required_value": "≥2414", "unit": "小时",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "项目年等效满负荷运行小时数不低于风机厂家承诺年发电小时数_2414小时。（P3348）"},
    # 4）集控远程系统及智慧电站建设
    {"id": "sp-013", "clause": "第五章2.性能指标4）", "page": "n/a-无分页",
     "requirement": "集控通信网络设备与操作系统国产化",
     "required_value": "通信网络设备选用国产设备；操作系统必须选用UNIX等国产操作系统", "unit": "",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "所有涉及到的通信网络设备选用国产设备，操作系统必须选用UNIX等国产操作系统，并进行漏洞补丁以及系统加固。配置电磁防护机柜，建设冗余通信通道。（P3350；P3352重申为LINUX）"},
    {"id": "sp-014", "clause": "第五章2.性能指标4）", "page": "n/a-无分页",
     "requirement": "电力监控系统安全防护等保测评",
     "required_value": "通过相关有资质单位等保测评验收", "unit": "",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "电力监控系统安全防护工作应当落实国家信息安全等级保护制度，按照国家信息安全等级保护的有关要求，坚持“安全分区、网络专用、横向隔离、纵向认证”的原则，保障电力监控系统的安全，并通过相关有资质单位等保测评验收。（P3352；P3351同）"},
    {"id": "sp-015", "clause": "第五章2.性能指标4）", "page": "n/a-无分页",
     "requirement": "无人值守智慧电站与集控中心端口预留",
     "required_value": "建设无人值守智慧电站；电站二次设备预留接入发包人上级单位集控中心的端口并满足集控功能", "unit": "",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "建设无人值守智慧电站，将站内的所有信息利用电力专线上传到大数据中心。电站二次设备需留存后续接入发包人上级单位集控中心的端口，并满足集控功能。（P3352）"},
    {"id": "sp-016", "clause": "第五章2.性能指标4）", "page": "n/a-无分页",
     "requirement": "电网调度数据网及通信系统设备按电网要求",
     "required_value": "按照当地电网的相关要求执行", "unit": "",
     "tolerance": "", "no_negative_allowed": True,
     "raw_text": "电网调度数据网和综合管理网以及通信系统设备，以及安装部署必须按照当地电网的相关要求执行。（P3353）"},
]

SOURCE = {"file": "示例发包人示例市100MW风电项目EPC总承包工程招标文件.docx",
          "page_range": "n/a-无分页（docx 无稳定页码，raw_text 尾部（Pxxxx）为段号锚点）。已抽：第五章「发包人要求」2.性能指标 P3333–P3353 全量 14 行（sp-003–sp-016，可量化 8 行）；挂起：第五章其余 8 节（1.总则/3.勘察设计/4.施工安装/5.风电场调试、试运行和验收/6.施工工期/7.施工质量/8.竣工试验与验收/9.工程管理）及其它章节技术规范"}


def build_01b():
    """序列化 01b_spec-items.json（契约 0.1，assets/spec-items.schema.json）。"""
    return {
        "schema_version": "0.1",
        "source": SOURCE,
        "items": SPEC_ITEMS,
    }


def main():
    ap = argparse.ArgumentParser(description="生成 01b_spec-items.json（技术规范条目抄行）")
    ap.add_argument("--bid", help="项目 bid 目录（与 --out 二选一）")
    ap.add_argument("--out", help="输出文件路径（与 --bid 二选一）")
    args = ap.parse_args()
    if not args.bid and not args.out:
        ap.error("必须指定 --bid 或 --out")
    p = os.path.join(args.bid, "01b_spec-items.json") if args.bid else args.out
    with open(p, "w", encoding="utf-8") as f:
        json.dump(build_01b(), f, ensure_ascii=False, indent=2)
    print("OK", p)
    print("⚠️ 2.性能指标节已全量（14 行，sp-003–sp-016）；第五章其余 8 节挂起中，"
          "不得冒充第五章全覆盖（共 %d 行，含合同条款/前附表来源 2 行）" % len(SPEC_ITEMS))


if __name__ == "__main__":
    main()
