# iwakuniTemporal

一个使用 **Python + Temporal** 实现的最小示例项目，用来演示：

- 从 **5 个公开文本来源** 抓取代理地址
- 做去重、格式清洗与数量限制
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

## 当前版本做了什么增强

相较于第一版的“纯模拟抓取”，当前版本已经改成：

- 真实请求 5 个公开代理列表文本源
- 自动去重
- 自动清洗 `http://`、`https://` 这类前缀
- 只保留 `IP:PORT` 格式的代理
- 默认只取前 `200` 条，避免 Workflow 结果过大
- 客户端启动时自动生成唯一 workflow ID，避免重复运行时撞 ID

## 代理来源

当前示例默认从下面 5 个公开文本源抓取：

1. `TheSpeedX`
2. `KangProxy`
3. `dpangestuw/Free-Proxy`
4. `thenasty1337/free-proxy-list`
5. `iplocate/free-proxy-list`

这些来源都在 `app/activities.py` 里的 `PROXY_SOURCE_URLS` 常量中，可以直接改。

## 说明

为了让你先看清 **Temporal 的工作方式**，这个示例目前仍然保留了**模拟测试逻辑**：

- 抓取来源：真实网络抓取
- L0 ~ L5：随机数模拟通过/失败、延迟
- 打分：示例算法
- DB：暂未接入

也就是说，这一版重点是：

**把“真实抓取 + Temporal 编排”连起来。**

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
        +--> 拉取来源 Activity（真实抓取 5 个来源）
        +--> 解析代理 Activity
        +--> L0 Activity
        +--> L1 Activity
        +--> L2 Activity
        +--> L3 Activity
        +--> L4 Activity
        +--> L5 Activity
        +--> 打分 Activity
```

## 为什么要限制抓取数量

真实公开代理列表常常很多，如果把几千条代理都直接放进一次 Workflow 返回值里，会让：

- 调试输出太大
- Workflow 负载变重
- 后续接数据库前不方便观察结果

所以示例版先默认限制为前 `200` 条。  
等你下一步要接数据库和批量并发时，再把这个上限改大，或者改成分页 / 分批流程。

## 下一步你可以怎么扩展

1. 把 `run_level_test` 改成真实的代理连通性测试
2. 在每一步 Activity 中把结果写入 PostgreSQL
3. 把当前串行子流程改成并发 child workflow
4. 增加失败重试、黑名单、地域筛选
5. 增加周期调度与自动淘汰逻辑

## 重点

这个仓库的目标不是“做一个完整代理池产品”，而是给你一个**足够小、但结构正确**的 Temporal 入门样板。

你后续如果要继续扩展，最自然的下一步一般是：

- **真实测试**
- **接数据库**
- **并发优化**
