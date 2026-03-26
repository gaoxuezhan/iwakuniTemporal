# iwakuniTemporal

一个使用 **Python + Temporal** 实现的最小示例项目，用来演示：

- 从多个来源抓取代理地址（示例里先用模拟数据）
- 按 **L0 -> L5** 顺序对代理进行测试
- 每一步记录测试结果
- 最后计算分数并筛选高分代理

## 项目结构

```text
.
├── README.md
├── requirements.txt
├── app
│   ├── __init__.py
│   ├── activities.py
│   ├── client_start.py
│   ├── worker.py
│   └── workflows.py
└── sample_data
    └── proxy_sources.txt
```

## 设计思路

这个示例把 **单个代理的完整测试流程** 写成一个 Temporal Workflow：

1. 拉取来源数据
2. 解析代理列表
3. 对每个代理执行子流程：
   - L0 测试
   - L1 测试
   - L2 测试
   - L3 测试
   - L4 测试
   - L5 测试
   - 汇总打分
4. 返回最终结果

## 说明

为了让你先看清 **Temporal 的工作方式**，这里先用了**模拟测试逻辑**，没有直接接 PostgreSQL、Redis、真实 HTTP 代理校验器。
后续你可以很容易替换为：

- 真正的 txt/http 来源抓取
- 真正的代理连通性校验
- DB 写入
- 更复杂的打分策略

## 运行步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 Temporal Server

你本地可以用官方开发模式，例如：

```bash
temporal server start-dev
```

如果你没有装 Temporal CLI，可以先参考官方文档安装。

### 3. 启动 Worker

```bash
python -m app.worker
```

### 4. 启动客户端，发起一次流程

```bash
python -m app.client_start
```

## 通信关系

```text
客户端 / 主干服务
        |
        v
 Temporal Workflow
        |
        +--> 拉取来源 Activity
        +--> 解析代理 Activity
        +--> L0 Activity
        +--> L1 Activity
        +--> L2 Activity
        +--> L3 Activity
        +--> L4 Activity
        +--> L5 Activity
        +--> 打分 Activity
```

## 下一步你可以怎么扩展

1. 把 `fetch_proxy_sources` 改成真正去 5 个 URL 下载 txt
2. 把 `run_level_test` 改成真实的代理测试
3. 在每一步 Activity 中把结果写入 PostgreSQL
4. 按地域、延迟、稳定性、匿名性做综合打分
5. 增加定时调度与批量并发

## 重点

这个仓库的目标不是“做一个完整代理池产品”，而是给你一个**足够小、但结构正确**的 Temporal 入门样板。
