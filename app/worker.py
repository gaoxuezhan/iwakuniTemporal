from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.activities import (
    calculate_proxy_score,
    fetch_proxy_sources,
    normalize_proxy_list,
    run_level_test,
)
from app.workflows import BatchProxyWorkflow, TestSingleProxyWorkflow


async def main() -> None:
    """启动 Temporal Worker。

    Worker 的职责：
    1. 监听指定 task queue
    2. 执行 Workflow 代码
    3. 执行 Activity 代码
    """

    # 默认连接本地开发环境中的 Temporal Server。
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="proxy-task-queue",
        workflows=[BatchProxyWorkflow, TestSingleProxyWorkflow],
        activities=[
            fetch_proxy_sources,
            normalize_proxy_list,
            run_level_test,
            calculate_proxy_score,
        ],
    )

    print("Worker 已启动，正在监听 task queue: proxy-task-queue")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
