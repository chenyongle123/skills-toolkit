#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-NC-4.0
"""mini_schema.py — 零依赖 JSON Schema 子集校验器（仅供本仓库测试使用）

设计原则：**遇到未支持的关键字直接报错**，绝不静默忽略。
静默忽略会让"校验通过"变成假绿——这比不校验更危险。
支持的子集：type / const / enum / pattern / minimum / maximum /
required / properties / additionalProperties / items。
其余关键字（$schema / $id / title / description / format / default）按元数据忽略。
"""
from __future__ import annotations

import re

IGNORED = {"$schema", "$id", "title", "description", "format", "default", "examples"}
SUPPORTED = {"type", "const", "enum", "pattern", "minimum", "maximum",
             "required", "properties", "additionalProperties", "items"}

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, name: str) -> bool:
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    py = _TYPES.get(name)
    if py is None:
        raise ValueError(f"mini_schema: 不支持的类型名 {name!r}")
    if name == "boolean":
        return isinstance(value, bool)
    return isinstance(value, py)


def validate(instance, schema: dict, path: str = "$") -> list[str]:
    """返回错误列表；空列表表示通过。"""
    unknown = set(schema) - SUPPORTED - IGNORED
    if unknown:
        raise ValueError(f"mini_schema: 未支持的关键字 {sorted(unknown)}（路径 {path}）")

    errors: list[str] = []

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: 应为常量 {schema['const']!r}，实为 {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} 不在允许集合 {schema['enum']}")

    if "type" in schema:
        names = schema["type"]
        names = [names] if isinstance(names, str) else list(names)
        if not any(_type_ok(instance, n) for n in names):
            errors.append(f"{path}: 类型应为 {names}，实为 {type(instance).__name__}")
            return errors  # 类型不符时后续约束无意义

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} 不匹配 {schema['pattern']}")
        if "minimum" in schema and len(instance) < schema["minimum"]:
            errors.append(f"{path}: 长度小于 {schema['minimum']}")
        if "maximum" in schema and len(instance) > schema["maximum"]:
            errors.append(f"{path}: 长度大于 {schema['maximum']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} 小于最小值 {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} 大于最大值 {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: 缺少必需字段 {key!r}")
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                errors += validate(value, props[key], f"{path}.{key}")
            else:
                addl = schema.get("additionalProperties", True)
                if addl is False:
                    errors.append(f"{path}: 不允许的字段 {key!r}")
                elif isinstance(addl, dict):
                    errors += validate(value, addl, f"{path}.{key}")

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errors += validate(item, schema["items"], f"{path}[{i}]")

    return errors
