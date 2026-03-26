from __future__ import annotations

import random
import time
from typing import Any

from temporalio import activity


@activity.defn
async def fetch_proxy_sources() -> list[str]:
    """模拟从多个来源抓取代理列表。

    这里先不访问真实网络，直接返回几条示例代理数据。
    你后续可以把这里改成：
    1. 请求 5 个 txt / http 来源
    2. 合并并去重
    3. 返回代理地址列表
    """

    # 这里故意 sleep 一下，模拟真实世界中的网络抓取耗时。
    time.sleep(1)

    return [
        "1.1.1.1:8080",
        "2.2.2.2:1080",
        "3.3.3.3:3128",
        "4.4.4.4:7890",
    ]


@activity.defn
async def normalize_proxy_list(raw_list: list[str]) -> list[dict[str, Any]]:
    """把原始代理字符串转换为结构化对象。

    返回的数据结构是后续 Workflow 里要一直传递的基础对象。
    """

    result: list[dict[str, Any]] = []
    for item in raw_list:
        host, port = item.split(":")
        result.append(
            {
                "proxy": item,
                "host": host,
                "port": int(port),
            }
        )
    return result


@activity.defn
async def run_level_test(proxy: str, level: str) -> dict[str, Any]:
    """执行某一层级的测试。

    参数：
    - proxy: 当前要测试的代理地址
    - level: 测试级别，例如 L0 / L1 / L2

    这里使用随机数模拟测试结果。
    在真实项目中，这里应该替换成：
    - TCP 连通性测试
    - HTTP 请求测试
    - HTTPS/TLS 测试
    - 匿名性测试
    - 延迟与稳定性测试
    """

    # 模拟测试耗时。
    time.sleep(0.5)

    # 为了让示例更接近真实情况，级别越高，通过概率越低。
    pass_rate_map = {
        "L0": 0.95,
        "L1": 0.85,
        "L2": 0.75,
        "L3": 0.60,
        "L4": 0.45,
        "L5": 0.30,
    }

    passed = random.random() < pass_rate_map[level]

    # 模拟一个延迟值，单位毫秒。
    latency_ms = random.randint(40, 500)

    return {
        "proxy": proxy,
        "level": level,
        "passed": passed,
        "latency_ms": latency_ms,
        "checked_at": int(time.time()),
    }


@activity.defn
async def calculate_proxy_score(proxy: str, level_results: list[dict[str, Any]]) -> dict[str, Any]:
    """根据各层测试结果计算总分。

    这只是一个简单演示版算法：
    - 每通过一层给固定基础分
    - 延迟越低，额外奖励越高
    - 一旦失败，后续层通常不会继续测试
    """

    total_score = 0
    details: list[dict[str, Any]] = []

    for item in level_results:
        level_score = 0
        if item["passed"]:
            # 每过一层先加 10 分。
            level_score += 10

            # 延迟越低，奖励越多；这里只做一个非常粗糙的近似公式。
            latency_bonus = max(0, 300 - item["latency_ms"]) / 30
            level_score += round(latency_bonus, 2)

        total_score += level_score
        details.append(
            {
                "level": item["level"],
                "passed": item["passed"],
                "latency_ms": item["latency_ms"],
                "level_score": level_score,
            }
        )

    # 简单示例：总分 >= 40，就认为是高分可用代理。
    is_candidate = total_score >= 40

    return {
        "proxy": proxy,
        "total_score": round(total_score, 2),
        "is_candidate": is_candidate,
        "details": details,
    }
