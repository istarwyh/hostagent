# hostagent PR #1 合并前验收（2026-10-09）

## 范围与基线

- PR：https://github.com/istarwyh/hostagent/pull/1
- 验收起点：`fa444d48b90a82c64f1e70be70f32f8c1c08aabe`。
- master：`8907f04fceb58a82cf05f1ef186c9bba46234ab8`，已包含在 PR 分支中；本地合并检查为 Already up to date。
- 原差异为 26 个提交、161 个文件，24681 行新增、2222 行删除。除标题中的 Assistant/checkpoint 改动，还包含 backend/frontend 目录迁移、LangChain v1 middleware、Agent pool、API/SSE/HITL 和前端界面。
- 按仓库此前已明确的实验项目范围验收：完整 checkout 运行。独立 wheel 分发不是要求；不重做架构，不部署生产环境。

## 验收修复

1. 用户 Assistant 创建和 PATCH 都不能通过 metadata 将 `created_by` 改成 system；系统身份由 registry 决定。
2. 旧 SimpleAuditToolNode 的 JSONL 汇总写入加进程内线程锁；新增 8 并发工作线程、40 条大记录的完整性测试。当前 v1 主路径 ToolAuditMiddleware 已有线程锁及平台文件锁。
3. 学习示例 `_set_env` 在无 TTY 时明确失败，避免后台交互等待。
4. 异步子 Agent 回归改用本地 FakeListChatModel，避免测试被本机代理或 SDK 客户端初始化依赖干扰；运行的仍是真实异步 LangGraph。
5. 原始 checkpoint 读取补全 SDK checkpoint/parent_checkpoint/tasks 字段，保留 checkpoint metadata；历史按最新状态在前返回，和绑定图路径一致，回归断言最新状态位于首项。
6. 前端 SDK 固定为实际兼容并验过的 1.0.3。仅按 package.json 的旧 caret 范围安装最新 SDK 1.12.3 时，`experimental_thread` 已不属于其 useStream 类型，tsc/build 会失败。

## 新增核心回归

`backend/src/test/test_pr_acceptance.py` 覆盖：

- 启动后注册新 Agent，HTTP 获取与搜索立即发现它。
- 系统 Agent PATCH/DELETE 均为 403，内容不变。
- 用户 Agent JSON 创建、PATCH、查询、删除和删除后 404，metadata 身份不能冒充系统。
- 真实图写入 MemorySaver 后，经绑定图与原始 checkpoint 两条读取路径，验证 messages、todos、files 各自保留；FileData 转换为前端字符串，含末尾换行。
- 指定 checkpoint 读取与当前状态一致；历史可读取完整状态；不同线程消息与文件互不污染；内部通道不泄漏。
- 旧审计节点并发汇总完整性，以及学习示例缺失配置时无交互等待。

## 评审核对

| 评审项 | 当前证据与判定 |
| --- | --- |
| Tavily 缺失导致 API 导入失败 | pyproject 已声明 tavily-python；干净 venv 安装成功，真实 TestClient API 启动及发现测试通过 |
| 创建/更新 JSON body 被忽略 | Pydantic 请求模型已落实；真实 HTTP 创建/改名/后续读取测试通过 |
| 用户 Assistant UUID 无法运行 | 共享 Assistant 服务解析 graph；创建→更新配置→流运行测试通过，run 覆盖 assistant 配置、线程 ID 不被注入覆盖 |
| values/updates 混合流错配 | 真实图混合 SSE 测试核对事件数量与形状，通过 |
| async 子 Agent 使用同步 invoke | 真实 async-only 图通过 ainvoke 回归；v1 多子 Agent/HITL 恢复测试通过 |
| 异常被审计 finally 覆盖 | 同步、异步失败工具测试保留原错误，审计记录落盘；output_content 已提前初始化 |
| 审计并发 | v1 middleware 已加锁并有并发测试；旧兼容节点本次补锁与回归 |
| 明文 Redis/provider 配置 | 当前代码使用环境变量，联网测试显式 opt-in；历史提交中旧凭证是否已撤销无法在本环境证实，也未尝试使用它们 |
| 学习示例缺失 key 时交互 | 本次增加 TTY 检查及独立回归 |
| 开发终端流预览吞异常、MCP 示例配置、unused imports/i18n/.DS_Store | 仍有历史线程未解决，属于开发示例、代码整洁项；不在 FastAPI 主运行路径，保留为非阻塞后续事项 |
| 仓库外 wheel 导入 | 所有者已撤回该范围要求，不作为阻塞 |

## 已知限制与无法验证部分

- 未配置真实模型/搜索服务凭证；不调用外部 provider。真实图、真实 API、实际 JS SDK 的本地契约验证不能证明模型效果或外部 MCP/Redis/Postgres 可用。
- 未完成浏览器里的人工视觉与交互验收；验证的是前端构建、类型和 SDK HTTP/SSE 契约。
- README 已明确：线程 state 写入仍为 501。前端文件编辑调用 updateState 会失败并显示保存错误；本次没有扩大范围实现该功能。文件读取与显示所需的字符串契约已验证。
- Assistant、thread、checkpoint 使用内存，不承诺重启或多 worker 持久化。旧审计节点补的是线程并发锁；多进程共享目录以 v1 主路径的文件锁能力为准。
- 未发现关联 PR GitHub Actions 记录；frontend/.github/workflows 位于子目录，不能当作仓库根工作流的 CI 成功证据。以本次本地命令结果为证。

## 验证命令与结果

- backend 干净 `.venv`：`uv pip install --python .venv/bin/python -e '.[dev]'` 成功。
- `python -m pytest -q --tb=short -W ignore::DeprecationWarning`：63 passed，1 skipped（显式 opt-in 联网测试）。最终本地回归不需清除代理变量。
- `ANTHROPIC_API_KEY=local-construction-placeholder OPENAI_API_KEY=local-construction-placeholder python -m pytest tests/test_middleware.py`：20 passed；客户端只构造不发外部请求，检查时清除当前环境 SOCKS 代理变量。
- `python -m compileall -q src`、`git diff --check`：通过。
- `node --test tests/*.test.mjs`：8 passed。
- 实际 SDK 1.0.3 + 本地 uvicorn + 真实无 provider 图：search、JSON create、user Assistant run、混合 SSE、getState、getHistory、delete 全链路通过。
- `npm run lint`：0 errors，4 条既有 fast-refresh warnings。
- 旧 Next 16.0.7 与 SDK 1.0.3：tsc 与生产构建通过；构建需 `NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS=1`，避免当前环境 Google Fonts TLS 下载错误。16.0.7 有已知安全问题，不作为放行版本。

## 最终前端依赖与结论

- Next.js 与 eslint-config-next 固定到 16.4.0；SDK 固定到 1.0.3，Yarn 锁文件同步。升级范围为同一 Next 主版本内的安全依赖及必要传递依赖，未改 UI 架构。
- 官方安全公告与 npm registry 的 advisory bulk API 证实原 16.0.7，以及仅升到 16.0.11，都不足以覆盖后续安全修复；因此没有放行旧版本。
- `yarn install --frozen-lockfile --offline --ignore-scripts --registry https://registry.npmjs.org`：成功，Already up-to-date。依赖先由正常 Yarn install 获取，本次冻结检查复用缓存；未绕过锁文件完整性。
- 在该锁定依赖安装上再次执行 `NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS=1 npm run build`：成功（Next 16.4.0，含 TypeScript 检查与静态页面生成）。
- 在该锁定依赖安装上再次执行前端 node tests 与 lint：8 passed；lint 0 errors、4 warnings。
- Yarn 有既有 @langchain/langgraph 的 zod peer warning，构建及实际使用的 SDK 契约通过；构建另有浏览器数据过旧提示。未借此批量升级无关依赖。
- 提交前再次从 GitHub 核对 master/head，均未变动，PR 仍 Open、mergeable；合并使用预期 head SHA，避免未验收代码被并入。

结论：在上述完整 checkout、内存存储、实验用途的范围内，关键回归和运行检查通过，没有剩余合并阻塞。保留已知限制，不把本次验收描述为生产环境或真实模型验收；允许合并，不执行生产部署。

安全参考：

- https://nextjs.org/blog/security-update-2025-12-11
- https://github.com/vercel/next.js/security/advisories
- https://registry.npmjs.org/-/npm/v1/security/advisories/bulk

