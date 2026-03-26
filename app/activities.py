from __future__ import annotations

import asyncio
import contextlib
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

# L0 的默认超时时间。
# 这里不要设太大，否则首次批量筛选会非常慢。
L0_CONNECT_TIMEOUT_SECONDS = 1.5

# L1 的 HTTP 测试超时时间。
L1_HTTP_TIMEOUT_SECONDS = 3.0

# L1 的目标页面。
# 这里故意选一个简单、稳定、纯 HTTP 的页面，方便验证“HTTP 代理是否真的能转发请求”。
L1_HTTP_TEST_URL = "http://example.com/"


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


async def _tcp_connect_probe(host: str, port: int, timeout_seconds: float) -> dict[str, Any]:
    """执行真实的 TCP 建连探测。

    这就是当前示例里的 L0 定义：
    - 能在超时内建立 TCP 连接，视为 L0 通过
    - 不能建立连接，视为 L0 失败

    这是一个非常基础但很有用的第一层筛选，能够快速剔除：
    - 端口根本不通的代理
    - 已经离线的代理
    - 响应极慢的代理
    """

    started = time.perf_counter()
    writer = None

    try:
        connect_task = asyncio.open_connection(host=host, port=port)
        reader, writer = await asyncio.wait_for(connect_task, timeout=timeout_seconds)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        # 这里只做“建连是否成功”的判断，不做任何协议级通信。
        # 因此 reader 这里先不使用，但保留变量名便于以后扩展。
        _ = reader

        return {
            "passed": True,
            "latency_ms": latency_ms,
            "error": None,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "passed": False,
            "latency_ms": latency_ms,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


def _http_proxy_request(proxy: str, test_url: str, timeout_seconds: float) -> dict[str, Any]:
    """通过 HTTP 代理访问一个 HTTP 页面。

    这是 L1 的核心动作：
    - 不只是看端口能否连上
    - 而是验证这个代理是否真的能转发一条 HTTP 请求

    这里使用 urllib 的 ProxyHandler，避免额外引入第三方依赖。
    """

    started = time.perf_counter()

    proxy_url = f"http://{proxy}"
    proxy_handler = urllib.request.ProxyHandler(
        {
            "http": proxy_url,
        }
    )
    opener = urllib.request.build_opener(proxy_handler)
    request = urllib.request.Request(
        test_url,
        headers={
            "User-Agent": "iwakuniTemporal/0.1 (+Temporal demo)",
            "Cache-Control": "no-cache",
        },
    )

    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            status_code = getattr(response, "status", response.getcode())
            body = response.read(512)

            return {
                "passed": 200 <= status_code < 400 and len(body) > 0,
                "latency_ms": latency_ms,
                "error": None,
                "status_code": status_code,
                "response_bytes": len(body),
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "passed": False,
            "latency_ms": latency_ms,
            "error": f"HTTPError: {exc.code} {exc.reason}",
            "status_code": exc.code,
            "response_bytes": 0,
            "final_url": test_url,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "passed": False,
            "latency_ms": latency_ms,
            "error": f"{type(exc).__name__}: {exc}",
            "status_code": None,
            "response_bytes": 0,
            "final_url": test_url,
        }


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

    当前版本的约定：
    - L0：真实 TCP 建连测试
    - L1：真实 HTTP 代理请求测试
    - L2 ~ L5：仍然使用随机数模拟

    这样做的原因是：
    - 先把最基础的两层真实筛选补上
    - 后续再逐层把 L2、L3... 替换成更真实的协议测试
    """

    host, port_text = proxy.split(":")
    port = int(port_text)

    if level == "L0":
        l0_result = await _tcp_connect_probe(
            host=host,
            port=port,
            timeout_seconds=L0_CONNECT_TIMEOUT_SECONDS,
        )

        return {
            "proxy": proxy,
            "level": level,
            "passed": l0_result["passed"],
            "latency_ms": l0_result["latency_ms"],
            "error": l0_result["error"],
            "check_type": "tcp_connect",
            "checked_at": int(time.time()),
        }

    if level == "L1":
        l1_result = await asyncio.to_thread(
            _http_proxy_request,
            proxy,
            L1_HTTP_TEST_URL,
            L1_HTTP_TIMEOUT_SECONDS,
        )

        return {
            "proxy": proxy,
            "level": level,
            "passed": l1_result["passed"],
            "latency_ms": l1_result["latency_ms"],
            "error": l1_result["error"],
            "check_type": "http_proxy_request",
            "target_url": L1_HTTP_TEST_URL,
            "status_code": l1_result["status_code"],
            "response_bytes": l1_result["response_bytes"],
            "final_url": l1_result["final_url"],
            "checked_at": int(time.time()),
        }

    # L2 以后目前仍然是演示版模拟逻辑。
    await asyncio.sleep(0.2)

    # 为了让示例更接近真实情况，级别越高，通过概率越低。
    pass_rate_map = {
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
        "error": None if passed else "simulated_failure",
        "check_type": "simulated",
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
                "error": item.get("error"),
                "check_type": item.get("check_type"),
                "status_code": item.get("status_code"),
                "target_url": item.get("target_url"),
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
