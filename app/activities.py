from __future__ import annotations

import asyncio
import random
import re
import time
import urllib.error
import urllib.request
from typing import Any

from temporalio import activity

# 这里放 5 个公开的代理文本来源。
# 后续你可以继续增加、替换或删除。
PROXY_SOURCE_URLS = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/xResults/Proxies.txt",
    "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/refs/heads/main/All_proxies.txt",
    "https://raw.githubusercontent.com/thenasty1337/free-proxy-list/main/data/latest/proxies.txt",
    "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/all-proxies.txt",
]

# 只保留最基础的 IP:PORT 形式。
# 这样后面的示例更容易看懂，也方便你后续接真实测试器。
IP_PORT_PATTERN = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}$")


def _download_text(url: str, timeout: int = 10) -> str:
    """同步下载文本内容。

    为什么这里做成同步函数？
    因为我们会在 async Activity 里通过 asyncio.to_thread 调它，
    这样不用额外安装 requests / aiohttp，也能并发抓取多个来源。
    """

    request = urllib.request.Request(
        url,
        headers={
            # 有些源会更愿意响应带浏览器风格 UA 的请求。
            "User-Agent": "iwakuniTemporal/0.1 (+Temporal demo)",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        # 大部分公开 txt 源都是 utf-8；遇到异常字符时直接忽略。
        return response.read().decode("utf-8", errors="ignore")


def _normalize_proxy_line(line: str) -> str | None:
    """把一行文本尽量清洗成标准的 IP:PORT。

    这里故意只做非常保守的清洗：
    - 去掉前后空白
    - 去掉 http:// / https:// / socks5:// 之类的协议前缀
    - 只取空白前的第一段
    - 最终只接受 IP:PORT
    """

    candidate = line.strip()
    if not candidate or candidate.startswith("#"):
        return None

    # 去掉协议前缀，例如 http://1.2.3.4:8080
    candidate = re.sub(r"^[a-zA-Z0-9+.-]+://", "", candidate)

    # 有些列表会在一行后面附带说明文字，这里只取第一个 token。
    candidate = candidate.split()[0]

    if not IP_PORT_PATTERN.match(candidate):
        return None

    return candidate


@activity.defn
async def fetch_proxy_sources(max_proxies: int = 200) -> list[str]:
    """从多个公开文本源抓取代理地址，并做去重与截断。

    参数：
    - max_proxies: 最多返回多少条代理。示例版默认 200，
      防止一次 Workflow 携带的数据过大，便于调试和观察。

    返回：
    - 形如 ["1.2.3.4:8080", "5.6.7.8:3128"] 的列表
    """

    # 并发抓取多个来源，提高速度。
    tasks = [
        asyncio.to_thread(_download_text, url, 10)
        for url in PROXY_SOURCE_URLS
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    proxies: list[str] = []
    seen: set[str] = set()

    for url, response in zip(PROXY_SOURCE_URLS, responses):
        if isinstance(response, Exception):
            activity.logger.warning("抓取来源失败: %s, error=%s", url, response)
            continue

        source_count = 0
        for raw_line in response.splitlines():
            proxy = _normalize_proxy_line(raw_line)
            if proxy is None:
                continue

            if proxy in seen:
                continue

            seen.add(proxy)
            proxies.append(proxy)
            source_count += 1

            if len(proxies) >= max_proxies:
                activity.logger.info("已达到最大抓取上限 %s，提前停止收集。", max_proxies)
                return proxies

        activity.logger.info("来源抓取完成: %s, 新增代理数=%s", url, source_count)

    if not proxies:
        raise RuntimeError("所有来源都抓取失败，或者没有解析出任何有效代理。")

    return proxies


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

    这里仍然使用随机数模拟测试结果。
    在真实项目中，这里应该替换成：
    - TCP 连通性测试
    - HTTP 请求测试
    - HTTPS/TLS 测试
    - 匿名性测试
    - 延迟与稳定性测试
    """

    # 模拟测试耗时。
    await asyncio.sleep(0.2)

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

    total_score = 0.0
    details: list[dict[str, Any]] = []

    for item in level_results:
        level_score = 0.0
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
