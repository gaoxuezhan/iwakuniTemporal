from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from temporalio.client import Client

from app.workflows import BatchProxyWorkflow


async def main() -> None:
    """客户端入口。

    作用：
    1. 连接 Temporal Server
    2. 启动一次批量测试 Workflow
    3. 等待结果并打印输出
    """

    client = await Client.connect("localhost:7233")

    # 真实 L0 建连测试比随机模拟更慢。
    # 为了让你第一次跑示例时不用等太久，这里先把默认数量降到 50。
    max_proxies = 50

    # 每次运行都生成唯一 ID，避免 Workflow ID 已存在导致启动失败。
    workflow_id = f"batch-proxy-workflow-{uuid4().hex[:8]}"

    handle = await client.start_workflow(
        BatchProxyWorkflow.run,
        max_proxies,
        id=workflow_id,
        task_queue="proxy-task-queue",
    )

    print(f"已启动 workflow，ID: {handle.id}")

    result = await handle.result()

    # 使用 json 美化输出，方便观察结构。
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
