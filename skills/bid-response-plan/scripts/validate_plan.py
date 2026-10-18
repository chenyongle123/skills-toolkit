# -*- coding: utf-8 -*-
"""
validate_plan.py —— ① bid-response-plan 产物契约校验（03/04/01b/03c/01c）
计划书 §6.2 契约 / 计划书 §5 目录树。

职责：对 ① 的全部 JSON 产物做 schema 校验（装了 jsonschema 走完整校验，
未安装降级为结构自检并 WARN——不假装通过，也不阻断生成）。
定位与 ⓪ 的 emit_facts 校验同款：**只报告差异，不自动修改**。

独立用法：python validate_plan.py --bid <项目>/bid [--only 03|04|01b|03c|01c]
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))

# 产物文件名 → (schema 名, 顶层必填键)
TARGETS = {
    "03": ("03_bid-plan.json", "bid-plan.schema.json", ["schema_version", "items", "coverage"]),
    "04": ("04_outline.json", "outline.schema.json", ["schema_version", "chapters"]),
    "01b": ("01b_spec-items.json", "spec-items.schema.json", ["schema_version", "source", "items"]),
    "03c": ("03c_business-forms.json", "business-forms.schema.json", ["schema_version", "forms"]),
    "01c": ("01c_format-outline.json", "format-outline.schema.json", ["schema_version", "chapters", "typography"]),
}


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def validate_one(bid, key):
    """返回 (结论串, 是否硬失败)。结论：ok / skip(no-file) / WARN:… / FAIL:…"""
    fname, sname, req = TARGETS[key]
    p = os.path.join(bid, fname)
    if not os.path.exists(p):
        return "skip(no-file: %s)" % fname, False
    data = load_json(p)
    # 结构自检（无论 jsonschema 是否可用都执行）
    missing = [k for k in req if k not in data]
    if missing:
        return "FAIL: 缺顶层键 %s" % ",".join(missing), True
    sp = os.path.join(ASSETS, sname)
    if not os.path.exists(sp):
        return "WARN: schema 缺失 %s，仅做结构自检" % sname, False
    try:
        import jsonschema
    except Exception:
        return ("WARN: jsonschema 未安装，%s 仅结构自检"
                "（安装后可获完整校验，见 SKILL.md 依赖说明）" % fname), False
    try:
        jsonschema.validate(data, load_json(sp))
        return "ok", False
    except Exception as e:
        return "FAIL: %s" % str(e)[:200], True


def main():
    ap = argparse.ArgumentParser(description="校验 ① 全部 JSON 产物与契约 schema")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--only", choices=sorted(TARGETS), help="只校验指定产物（默认全部）")
    args = ap.parse_args()
    keys = [args.only] if args.only else list(TARGETS)
    failed = False
    for k in keys:
        res, hard = validate_one(args.bid, k)
        if hard:
            failed = True
        print("%-4s %-26s %s" % (k, TARGETS[k][0], res))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
