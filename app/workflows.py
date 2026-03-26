from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities import (
        calculate_proxy_score,
        fetch_proxy_sources,
        normalize_proxy_list,
        run_level_test,
    )


@workflow.defn
class TestSingleProxyWorkflow:
    """单个代理测试工作流。

    这个 Workflow 负责一条代理的完整生命周期：
    L0 -> L1 -> L2 -> L3 -> L4 -> L5 -> 打分

    设计原则：
    - 前一层失败，后续就不再继续
    - 每一层测试都由 Activity 执行
    - 最终把所有结果汇总后返回
    """

    @workflow.run
    async def run(self, proxy: str) -> dict[str, Any]:
        level_results: list[dict[str, Any]] = []

        for level in ["L0", "L1", "L2", "L3", "L4", "L5"]:
            result = await workflow.execute_activity(
                run_level_test,
                args=[proxy, level],
                start_to_close_timeout=timedelta(seconds=10),
            )
            level_results.append(result)

            # 如果当前层失败，就直接停止后续测试。
            if not result["passed"]:
                break

        score_result = await workflow.execute_activity(
            calculate_proxy_score,
            args=[proxy, level_results],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return {
            "proxy": proxy,
            "level_results": level_results,
            "score_result": score_result,
        }


@workflow.defn
class BatchProxyWorkflow:
    """批量代理测试工作流。

    这个 Workflow 先抓取代理来源，再把每条代理作为一个子流程处理。
    在真实生产环境里，你可以：
    - 增加批量并发控制
    - 增加数据库写入
    - 增加失败重试策略
    - 增加去重和黑名单逻辑
    """

    @workflow.run
    async def run(self) -> dict[str, Any]:
        raw_sources = await workflow.execute_activity(
            fetch_proxy_sources,
            start_to_close_timeout=timedelta(seconds=10),
        )

        proxies = await workflow.execute_activity(
            normalize_proxy_list,
            args=[raw_sources],
            start_to_close_timeout=timedelta(seconds=10),
        )

        results: list[dict[str, Any]] = []

        # 这里先串行执行，便于你理解流程。
        # 后续你完全可以改成并发启动多个 child workflow。
        for item in proxies:
            child_result = await workflow.execute_child_workflow(
                TestSingleProxyWorkflow.run,
                item["proxy"],
                id=f"test-proxy-{item['host']}-{item['port']}",
            )
            results.append(child_result)

        candidates = [
            item
            for item in results
            if item["score_result"]["is_candidate"]
        ]

        return {
            "total": len(results),
            "candidates": candidates,
            "all_results": results,
        }
