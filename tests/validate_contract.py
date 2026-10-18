#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-NC-4.0
"""validate_contract.py — 套件契约与一致性校验（零依赖）

用法：
    python tests/validate_contract.py            # 只校验，失败退出 1
    python tests/validate_contract.py --write-lock  # 重新生成 skills-lock.json

校验项（对应计划书 §11.1 阶段 0 验收）：
  C1 五技能 frontmatter version 实读，且与 skills-lock.json 一致
  C2 共用 schema 各副本 sha256 一致，且与 lock 记录一致
  C3 四份 SKILL.md 的 8 条铁律块逐字一致（IRONLAWS 标记间内容）
  C4 四份 流水线交接约定.md sha256 一致
  C5 七份 JSON fixture 通过对应 schema（mini_schema 子集校验）
  C5b 02_facts.sample.yaml 对照 facts.schema.yaml 做结构校验（此前 fixture 未被校验，套件盲审 #2）
  C6 03c 商务表框架不含金额数字
  C7 ⓪ 保护区仍在位（11 条铁律 / 7 步流程 / 七类输出格式）
  C8 description 触发词无重复短语（静态检查；平台实测另见阶段 0 验收记录）
  C9 四技能 SKILL.md 的入口 stage、下一技能指路、交接约定引用齐备（防"声称接好了实际没接"）
  C10 铁律块与计划书 §7 原文一致（唯一真源比对；计划书不在时跳过并提示）
  C11 03 的补遗对照前置项在位且合法（p-0001 / 三态 / blocking / 非 pass 须有证据）
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# 本地隔离依赖：PyYAML 仅用于 facts.yaml 契约为 YAML 的校验（零依赖原则下不外装到系统）
_VENDOR = Path(__file__).resolve().parent / "_vendor"
if _VENDOR.is_dir():
    sys.path.insert(0, str(_VENDOR))
import mini_schema  # noqa: E402

try:
    import yaml  # PyYAML；仅用于 facts.schema.yaml / 02_facts.sample.yaml 的校验，缺失时 C5b 跳过
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
FIXTURES = Path(__file__).parent / "fixtures"
LOCK = ROOT / "skills-lock.json"

FIVE = ["tender-document-review", "bid-response-plan",
        "bid-compliance-check", "bid-technical-proposal", "bid-docx-export"]
FOUR = FIVE[1:]

# 阶段 0 的 7 个契约 schema（§5.2 前 7 行）：文件名 → 副本所属技能
SCHEMAS = {
    "metadata.schema.json": ["bid-response-plan", "bid-compliance-check",
                             "bid-technical-proposal", "bid-docx-export"],
    "tender-facts.schema.json": ["tender-document-review", "bid-response-plan"],
    "facts.schema.yaml": ["bid-response-plan", "bid-compliance-check", "bid-technical-proposal"],
    "spec-items.schema.json": ["bid-response-plan"],
    "format-outline.schema.json": ["bid-response-plan"],
    "bid-plan.schema.json": ["bid-response-plan"],
    "business-forms.schema.json": ["bid-response-plan"],
    "compliance-report.schema.json": ["bid-compliance-check"],
}

# schema 文件 → (fixture, 是否用 mini_schema 校验)
FIXTURE_MAP = {
    "metadata.schema.json": ["00_metadata.min.json", "00_metadata.full.json"],
    "tender-facts.schema.json": ["01_tender-facts.sample.json"],
    "spec-items.schema.json": ["01b_spec-items.sample.json"],
    "format-outline.schema.json": ["01c_format-outline.sample.json"],
    "bid-plan.schema.json": ["03_bid-plan.sample.json"],
    "business-forms.schema.json": ["03c_business-forms.sample.json"],
    "compliance-report.schema.json": ["06_compliance.sample.json"],
}

errors: list[str] = []
notes: list[str] = []


def err(code: str, msg: str) -> None:
    errors.append(f"[{code}] {msg}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_version(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", text, re.M)
    if not m:
        raise SystemExit(f"无法从 {skill}/SKILL.md 实读 version")
    return m.group(1)


def description(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^description:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def ironlaws(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"<!-- IRONLAWS:BEGIN -->(.*?)<!-- IRONLAWS:END -->", text, re.S)
    if not m:
        raise SystemExit(f"{skill}/SKILL.md 缺少 IRONLAWS 标记")
    return m.group(1).strip()


# ---------- C1 / C2 ----------
def check_versions_and_hashes(compare: bool = True) -> dict:
    lock = {"skills": {}, "schemas": {}}
    for s in FIVE:
        lock["skills"][s] = {"version": read_version(s)}
    for name, owners in SCHEMAS.items():
        hashes = {}
        for owner in owners:
            p = SKILLS / owner / "assets" / name
            if not p.exists():
                err("C2", f"缺少 schema 副本：{owner}/assets/{name}")
                continue
            hashes[owner] = sha256(p)
        if len(set(hashes.values())) > 1:
            err("C2", f"{name} 副本 hash 不一致：{ {k: v[:8] for k, v in hashes.items()} }")
        if hashes:
            lock["schemas"][name] = {
                "hash": sorted(hashes.values())[0],
                "copies": owners,
            }
    if not compare:
        # --write-lock：只采集现值，不与旧 lock 比对（否则改版即被自己的记录卡死）
        return lock
    if LOCK.exists():
        old = json.loads(LOCK.read_text(encoding="utf-8"))
        for s, rec in lock["skills"].items():
            o = old.get("skills", {}).get(s, {})
            if o and o.get("version") != rec["version"]:
                err("C1", f"{s} 版本不一致：lock={o.get('version')} 实读={rec['version']}")
        for name, rec in lock["schemas"].items():
            o = old.get("schemas", {}).get(name, {})
            if o and o.get("hash") != rec["hash"]:
                err("C2", f"{name} 与 lock 记录不一致（实读 {rec['hash'][:8]} / lock {o.get('hash','')[:8]}）")
    else:
        notes.append("skills-lock.json 不存在（可用 --write-lock 生成）")
    return lock


# ---------- C3 / C4 ----------
def check_verbatim() -> None:
    base = ironlaws(FOUR[0])
    for s in FOUR[1:]:
        if ironlaws(s) != base:
            err("C3", f"{s} 的 8 条铁律与 {FOUR[0]} 不逐字一致")
    if base.count("\n8. ") == 0:
        err("C3", "铁律块未包含第 8 条")

    conv = [sha256(SKILLS / s / "references" / "流水线交接约定.md") for s in FOUR]
    if len(set(conv)) != 1:
        err("C4", "四份 流水线交接约定.md hash 不一致")


# ---------- C5 / C6 ----------
def check_schemas_and_fixtures() -> None:
    for name, fixtures in FIXTURE_MAP.items():
        owners = SCHEMAS.get(name)
        if not owners:
            err("C5", f"{name} 未登记 SCHEMAS owner，无法定位 schema 副本")
            continue
        schema_path = SKILLS / owners[0] / "assets" / name
        if not schema_path.exists():
            err("C5", f"schema 缺失：{schema_path}")
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for fx in fixtures:
            p = FIXTURES / fx
            if not p.exists():
                err("C5", f"fixture 缺失：{fx}")
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            for e in mini_schema.validate(data, schema):
                err("C5", f"{fx}（{name}）：{e}")

    # C6：03c 不得含金额数字。只扫「承载内容」的字段，排除 id / 路径 / 章节 id（n-1000 不是金额）
    bf = json.loads((FIXTURES / "03c_business-forms.sample.json").read_text(encoding="utf-8"))
    amount = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:元|万元)|\d{4,}(?:\.\d+)?")
    for form in bf.get("forms", []):
        for key in ("name", "seal"):
            if isinstance(form.get(key), str) and amount.search(form[key]):
                err("C6", f"{form.get('id')}.{key} 含疑似金额：{amount.search(form[key]).group(0)}")
        for fld in form.get("required_fields", []):
            if amount.search(fld):
                err("C6", f"{form.get('id')}.required_fields 含疑似金额：{amount.search(fld).group(0)}")
    for rule in bf.get("consistency_rules", []):
        if amount.search(rule):
            err("C6", f"consistency_rules 含具体数值：{amount.search(rule).group(0)}")


# ---------- C5b ----------
def check_facts_fixture() -> None:
    """C5b：02_facts.sample.yaml 对照 facts.schema.yaml（自定义声明式契约）做结构校验。

    背景：FIXTURE_MAP 只覆盖 JSON-schema 类契约；facts 是 YAML 自定义格式，
    其 fixture 此前存在于 fixtures/ 却未被任何检查引用——验收记录"7 schema 全通过"
    对 facts 不成立（套件盲审 #2）。此处补实例校验，使其不再孤儿。
    """
    if yaml is None:
        notes.append("PyYAML 不可用，C5b 跳过（需运行时安装 PyYAML）")
        return
    schema_path = SKILLS / "bid-response-plan" / "assets" / "facts.schema.yaml"
    data_path = FIXTURES / "02_facts.sample.yaml"
    if not schema_path.exists():
        err("C5", f"facts schema 缺失：{schema_path}")
        return
    if not data_path.exists():
        err("C5", f"facts fixture 缺失：{data_path}")
        return
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    data = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    common_req = list(schema.get("common_required", []))
    sections = schema.get("sections", {})
    if not isinstance(data, dict):
        err("C5", "02_facts.sample.yaml 顶层应为映射")
        return
    for sec_name, sec_def in sections.items():
        items = data.get(sec_name)
        if not isinstance(items, list):
            err("C5", f"02_facts.{sec_name} 应为列表，实为 {type(items).__name__}")
            continue
        req = list(common_req) + [f for f, spec in sec_def.get("fields", {}).items()
                                  if spec.get("required")]
        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                err("C5", f"02_facts.{sec_name}[{idx}] 非对象")
                continue
            for f in req:
                if f not in it:
                    err("C5", f"02_facts.{sec_name}[{idx}] 缺必填字段 {f}")


# ---------- C7 ----------
def check_upstream_protected() -> None:
    text = (SKILLS / "tender-document-review" / "SKILL.md").read_text(encoding="utf-8")
    for n in range(1, 12):
        if not re.search(rf"^\|\s*\*\*{n}\*\*\s*\|", text, re.M) and \
           not re.search(rf"^\s*{n}\.\s+\*\*", text, re.M):
            err("C7", f"⓪ 保护区：未找到第 {n} 条铁律")
    steps = len(re.findall(r"^###\s*第\s*\d\s*步", text, re.M))
    if steps < 7:
        err("C7", f"⓪ 保护区：7 步流程仅找到 {steps} 步")
    if text.count("| ① ") < 1 or text.count("| ⑦ ") < 1:
        err("C7", "⓪ 保护区：七类输出格式表疑似缺失")


# ---------- C8 ----------
STOP = {"投标文件", "招标文件", "投标", "招标", "文件", "标书", "做", "写", "检查", "分析"}


def triggers(desc: str) -> set[str]:
    """只取「当用户…时使用」这一段里的触发短语——正文里的名词引用不算触发词。"""
    seg = re.search(r"当用户(.*?)(?:时使用|时调用|时加载)", desc)
    text = seg.group(1) if seg else desc
    quoted = set(re.findall(r"[\"“]([^\"”]{2,12})[\"”]", text))
    quoted |= set(re.findall(r"「([^」]{2,12})」", text))
    return {q.strip() for q in quoted if q.strip() and q.strip() not in STOP}


def check_routing() -> None:
    seen: dict[str, str] = {}
    for s in FIVE:
        for t in triggers(description(s)):
            if t in seen and seen[t] != s:
                err("C8", f"触发短语重复：{t!r} 同时出现在 {seen[t]} 与 {s}")
            seen[t] = s
    if "不编写投标材料" not in description("tender-document-review") and \
       "只审查招标文件" not in description("tender-document-review"):
        err("C8", "⓪ description 缺少「只审查招标文件」的边界声明（会与 ① 抢触发）")


# ---------- C9 ----------
ENTRY = {
    "bid-response-plan": ["reviewed", "facts_confirmed"],
    "bid-compliance-check": ["plan_confirmed", "writing"],
    "bid-technical-proposal": ["check_confirmed"],
    "bid-docx-export": ["recheck_confirmed"],
}
NEXT = {
    "bid-response-plan": "bid-compliance-check",
    "bid-compliance-check": "bid-technical-proposal",
    "bid-technical-proposal": "bid-compliance-check",
    "bid-docx-export": None,  # 链路终点，无下一技能（C9 改为校验"收口"声明，见下）
}
STAGES = {"reviewed", "facts_confirmed", "planning", "plan_confirmed", "checking",
          "check_confirmed", "route_confirmed", "writing", "rechecking",
          "recheck_confirmed", "exported", "exhausted"}


def check_handoff() -> None:
    for s in FOUR:
        text = (SKILLS / s / "SKILL.md").read_text(encoding="utf-8")
        for st in ENTRY[s]:
            if st not in STAGES:
                err("C9", f"{s} 引用了状态机中不存在的 stage：{st}")
            elif f"`{st}`" not in text:
                err("C9", f"{s} 未声明入口 stage {st}")
        if NEXT[s] is None:
            # 链路终点（④）：不指路下一技能，必须显式声明"收口"，否则降级检查形同虚设
            terminal = ("收口" in text or "无下一技能" in text or "终点" in text
                        or "已是最后一环" in text or "链路在本技能收口" in text)
            if not terminal:
                err("C9", f"{s} 是链路终点，但 SKILL.md 未声明「收口/无下一技能」")
        elif NEXT[s] not in text:
            err("C9", f"{s} 出口未指路 {NEXT[s]}")
        if "流水线交接约定.md" not in text:
            err("C9", f"{s} 未引用 references/流水线交接约定.md")
        if "入口校验" not in text:
            err("C9", f"{s} 缺少入口校验节")


# ---------- C10 ----------
def check_against_plan() -> None:
    plans = list(ROOT.glob("docs/投标文件Skill建设计划_v*.md"))
    if not plans:
        notes.append("未找到计划书，C10 跳过（独立安装场景属正常）")
        return
    def vkey(p: Path):
        m = re.search(r"_v(\d+)\.(\d+)\.md$", p.name)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    plan = max(plans, key=vkey)
    text = plan.read_text(encoding="utf-8")
    m = re.search(r"## 7\. 铁律.*?\n\n(.*?)\n\n> 每条铁律", text, re.S)
    if not m:
        err("C10", f"{plan.name} 未找到 §7 铁律段")
        return
    norm = lambda t: re.sub(r"\s+", "", t)
    if norm(m.group(1)) != norm(ironlaws(FOUR[0])):
        err("C10", f"SKILL.md 铁律块与 {plan.name} §7 不一致（唯一真源是计划书）")
    else:
        notes.append(f"C10 已比对 {plan.name} §7")


# ---------- C11 ----------
def check_preconditions() -> None:
    """C11：03 的补遗对照前置项在位且合法（v0.2 契约的操作性约束）。

    这条机检的存在意义：schema 只要求 preconditions 若出现则字段合法，不强求出现；
    但计划书 §4.1 要求补遗对照"必须有"。若只靠 schema，删掉整块也能通过校验——
    故在此加一道存在性检查，避免 0.2 契约退化为"写了没人管"。
    """
    p = FIXTURES / "03_bid-plan.sample.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != "0.2":
        err("C11", f"03 fixture 的 schema_version 应为 0.2，实为 {data.get('schema_version')}")
    pcs = data.get("preconditions")
    if not isinstance(pcs, list) or not pcs:
        err("C11", "03 fixture 缺 preconditions（补遗对照无落点）")
        return
    ids = [x.get("id") for x in pcs]
    if len(ids) != len(set(ids)):
        err("C11", f"preconditions 的 id 有重复：{ids}")
    first = pcs[0]
    if first.get("id") != "p-0001":
        err("C11", "preconditions 首项必须是 p-0001（补遗对照为固定首位，不得被挤后）")
    if "补遗" not in first.get("item", ""):
        err("C11", f"p-0001 的 item 应含「补遗」，实为「{first.get('item')}」")
    if first.get("result") not in {"pass", "fail", "unknown"}:
        err("C11", f"p-0001 的 result 非法：{first.get('result')}")
    if first.get("blocking") is not True:
        err("C11", "p-0001 的 blocking 必须为 true（补遗未对照即整份阻断）")
    for x in pcs:
        if x.get("result") != "pass" and not x.get("evidence"):
            err("C11", f"{x.get('id')} result≠pass 却无 evidence，判定不可信")


def main() -> int:
    write_lock = "--write-lock" in sys.argv
    lock = check_versions_and_hashes(compare=not write_lock)
    check_verbatim()
    check_schemas_and_fixtures()
    check_facts_fixture()
    check_upstream_protected()
    check_routing()
    check_handoff()
    check_against_plan()
    check_preconditions()

    if write_lock and not errors:
        tz = timezone(timedelta(hours=8))
        # kit_version 是人工维护的阶段标记（stage0/stage1…），--write-lock 只机器采集
        # 版本与 schema 现值，保留旧值；仅当 lock 不存在时落初始值
        old_kit = "kit/v0.1.0-stage0"
        if LOCK.exists():
            try:
                old_kit = json.loads(LOCK.read_text(encoding="utf-8")).get("kit_version", old_kit)
            except Exception:
                pass
        lock = {
            "kit_version": old_kit,
            "generated_at": datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "skills": lock["skills"],
            "schemas": lock["schemas"],
        }
        LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已写出 {LOCK.relative_to(ROOT)}")

    for n in notes:
        print(f"NOTE  {n}")
    if errors:
        print(f"\nFAIL  {len(errors)} 项")
        for e in errors:
            print("  " + e)
        return 1
    print("\nPASS  阶段 0 契约校验全部通过")
    print("  技能版本：" + "，".join(f"{k}={v['version']}" for k, v in lock["skills"].items()))
    print("  schema  ：" + "，".join(lock["schemas"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
