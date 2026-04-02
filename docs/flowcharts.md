# 流程图

这个文件把 `iwakuniTemporal` 当前版本的核心流程，整理成可以直接在 GitHub 渲染的 Mermaid 图。

## 1. 整体通信图

```mermaid
flowchart TD
    U[用户 / 前端] -->|HTTP| O[主干服务 / Orchestrator / Client]
    O -->|Start / Query Workflow| T[Temporal Service]

    T -->|调度 Activity / Child Workflow| BW[BatchProxyWorkflow]
    BW --> A1[fetch_proxy_sources Activity\n真实抓取 5 个来源]
    BW --> A2[normalize_proxy_list Activity\n解析代理列表]
    BW --> CW[TestSingleProxyWorkflow\n每个代理一个子流程]

    CW --> L0[L0 Activity\n真实 TCP 建连测试]
    L0 -->|通过| L1[L1 Activity\n真实 HTTP 代理请求测试]
    L0 -->|失败| SCORE[calculate_proxy_score Activity]

    L1 -->|通过| L2[L2 Activity\n模拟]
    L1 -->|失败| SCORE
    L2 -->|通过| L3[L3 Activity\n模拟]
    L2 -->|失败| SCORE
    L3 -->|通过| L4[L4 Activity\n模拟]
    L3 -->|失败| SCORE
    L4 -->|通过| L5[L5 Activity\n模拟]
    L4 -->|失败| SCORE
    L5 --> SCORE

    SCORE --> R[返回单代理结果]
    R --> BW
    BW --> OUT[返回批量结果\n候选代理 / 全量结果]
```

## 2. 单个代理执行流图

```mermaid
flowchart TD
    START[开始 TestSingleProxyWorkflow] --> L0A[L0\n真实 TCP 建连测试]

    L0A -->|失败| SCOREA[打分并结束]
    L0A -->|通过| L1A[L1\n真实 HTTP 代理请求测试]

    L1A -->|失败| SCOREA
    L1A -->|通过| L2A[L2\n模拟测试]

    L2A -->|失败| SCOREA
    L2A -->|通过| L3A[L3\n模拟测试]

    L3A -->|失败| SCOREA
    L3A -->|通过| L4A[L4\n模拟测试]

    L4A -->|失败| SCOREA
    L4A -->|通过| L5A[L5\n模拟测试]

    L5A --> SCOREA
    SCOREA --> END[结束并返回结果]
```

## 3. 读图说明

当前版本的层级含义：

- `L0`：代理地址的 `host:port` 能否完成 TCP 建连
- `L1`：该代理能否真的转发一条 HTTP 请求
- `L2 ~ L5`：目前还是演示用模拟逻辑，后续可以逐层替换成真实测试

## 4. 为什么 Temporal 版适合这种图

因为在 Temporal 里：

- 批量流程是 `BatchProxyWorkflow`
- 单代理流程是 `TestSingleProxyWorkflow`
- 真正动作是 `Activity`

所以图画出来以后，和代码结构几乎是一一对应的。后续你继续扩展 L2 / L3 / 数据库写入 / 并发 child workflow 时，也比较容易继续维护这份图。
