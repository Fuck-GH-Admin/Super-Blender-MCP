# Blender MCP Official - 架构概览

> 源码来源: [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) (22k+ stars)
> 作者: Siddharth Ahuja | 许可: MIT | 版本: 1.5.5

## 1. 系统拓扑

```
┌─────────────────┐     stdio      ┌─────────────────────┐     TCP:9876     ┌─────────────────────┐
│   MCP Client    │ ──────────────>│   FastMCP Server    │ ───────────────>│   Blender Addon     │
│ (Claude Desktop)│<────────────── │   (server.py)       │<─────────────── │   (addon.py)        │
│                 │   JSON-RPC     │   1186 lines        │   JSON over TCP │   2636 lines        │
└─────────────────┘                └─────────────────────┘                 └─────────────────────┘
                                           │                                        │
                                           │ Supabase                               │ bpy API
                                           v                                        v
                                   ┌───────────────┐                       ┌─────────────────┐
                                   │  Telemetry    │                       │  Blender 3D     │
                                   │  (Supabase)   │                       │  Application    │
                                   └───────────────┘                       └─────────────────┘
```

## 2. 核心组件

### 2.1 MCP Server (`src/blender_mcp/server.py`, 1186行)

**框架**: FastMCP (基于 `mcp.server.fastmcp.FastMCP`)

**实例化** (line 208):
```python
mcp = FastMCP("BlenderMCP", lifespan=server_lifespan)
```

**生命周期管理** (`server_lifespan()`, lines 171-205):
- 异步上下文管理器
- 启动时: 记录遥测事件, 尝试连接 Blender
- 关闭时: 断开全局连接

**全局连接模式**:
- `_blender_connection` (line 216): 模块级单例
- `get_blender_connection()` (lines 219-251):
  - 检查现有连接是否存活（发送 `get_polyhaven_status` 作为 ping）
  - 如果连接已死，创建新连接
  - 支持 `BLENDER_HOST` / `BLENDER_PORT` 环境变量

**BlenderConnection 数据类** (lines 30-169):
- `connect()`: 创建 TCP socket 连接
- `disconnect()`: 关闭 socket
- `receive_full_response()`: 分块接收 JSON 响应，180秒超时
- `send_command(command_type, params)`: 发送 JSON 命令并等待响应

**工具函数特征**:
- 所有工具函数都是**同步**的
- 使用 `@mcp.tool()` 和 `@telemetry_tool("tool_name")` 双重装饰器
- 通过全局连接发送命令

### 2.2 Blender Addon (`addon.py`, 2636行)

**BlenderMCPServer 类** (lines 39-2321):

**TCP 服务器**:
- 守护线程运行 (`_server_loop`, line 93)
- 每个客户端连接一个独立线程 (`_handle_client`, line 126)
- 关键: 通过 `bpy.app.timers.register(execute_wrapper, first_interval=0.0)` (line 170) 将命令调度到 Blender 主线程执行

**命令分发** (`_execute_command_internal()`, lines 196-267):
- 基于字典的 handler 分发
- 条件注册: PolyHaven、Hyper3D、Sketchfab、Hunyuan3D 的 handler 仅在 UI 中启用时注册

**UI 面板** (lines 2323-2636):
- 侧边栏面板: `View3D > Sidebar > BlenderMCP`
- 端口配置、集成开关、API 密钥输入
- 连接/断开按钮

### 2.3 Telemetry 系统 (`telemetry.py`, 343行)

**TelemetryCollector 类**:
- 后台工作线程 + 事件队列（最大 1000 事件）
- Supabase 作为后端
- 匿名 UUID 持久化存储在平台特定目录
- 感知用户同意状态（通过 Blender 偏好设置）
- 可通过环境变量禁用: `DISABLE_TELEMETRY`, `BLENDER_MCP_DISABLE_TELEMETRY`, `MCP_DISABLE_TELEMETRY`

### 2.4 Prompt 系统

`asset_creation_strategy()` prompt (lines 1089-1177):
- 定义资产创建工作流
- 优先级: Sketchfab > PolyHaven > Hyper3D > Hunyuan3D > 脚本回退

## 3. 数据流

```
1. Claude 调用 MCP 工具 (如 execute_blender_code)
2. Server 工具函数调用 get_blender_connection().send_command("execute_code", {"code": code})
3. send_command() 序列化为 JSON {"type": "execute_code", "params": {"code": "..."}} 通过 TCP 发送
4. Blender addon 的 _handle_client() 接收 JSON，解析
5. 通过 bpy.app.timers.register() 调度到主线程
6. execute_wrapper -> execute_command() -> _execute_command_internal() 分发到对应 handler
7. handler 执行 Blender API 调用
8. 响应字典序列化为 JSON 通过 TCP 返回
9. MCP server 接收 JSON 响应并返回给 Claude
```

## 4. 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BLENDER_HOST` | `localhost` | Blender addon 监听地址 |
| `BLENDER_PORT` | `9876` | Blender addon 监听端口 |
| `DISABLE_TELEMETRY` | - | 禁用遥测 |
| `BLENDER_MCP_DISABLE_TELEMETRY` | - | 禁用遥测 |
| `MCP_DISABLE_TELEMETRY` | - | 禁用遥测 |

## 5. 项目结构

```
blender-mcp-official/
├── main.py                          # 入口点 (8行)
├── addon.py                         # Blender 插件 (2636行)
├── pyproject.toml                   # 项目配置
├── assets/
│   ├── addon-instructions.png       # UI 截图
│   └── hammer-icon.png             # 工具图标
└── src/
    └── blender_mcp/
        ├── __init__.py              # 包初始化 (6行)
        ├── server.py                # MCP 服务器 (1186行)
        ├── telemetry.py             # 遥测收集器 (343行)
        └── telemetry_decorator.py   # 遥测装饰器 (66行)
```
