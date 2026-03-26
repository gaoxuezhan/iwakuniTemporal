from __future__ import annotations

import asyncio
import json

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

    handle = await client.start_workflow(
        BatchProxyWorkflow.run,
        id="batch-proxy-workflow-demo",
        task_queue="proxy-task-queue",
    )

    print(f"已启动 workflow，ID: {handle.id}")

    result = await handle.result()

    # 使用 json 美化输出，方便观察结构。
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
