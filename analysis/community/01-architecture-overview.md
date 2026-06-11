# Blender MCP Community - 架构概览

> 源码来源: [dhakalnirajan/blender-open-mcp](https://github.com/dhakalnirajan/blender-open-mcp) (100 stars)
> 作者: Nirajan Dhakal | 许可: MIT | 版本: 2.0.0

## 1. 系统拓扑

```
┌─────────────────┐   HTTP/JSON-RPC  ┌─────────────────────┐   TCP:9876     ┌─────────────────────┐
│   MCP Client    │ ────────────────>│   FastMCP Server    │ ─────────────>│   Blender Addon     │
│ (Claude Desktop)│<──────────────── │   (server.py)       │<───────────── │   (addon.py)        │
│  或 client.py   │   stdio/http     │   1044 lines        │   JSON+newline│   655 lines         │
└─────────────────┘                  └─────────────────────┘               └─────────────────────┘
                                           │                                        │
                                           │ httpx                                   │ bpy API
                                           v                                        v
                                   ┌───────────────┐                       ┌─────────────────┐
                                   │    Ollama     │                       │  Blender 3D     │
                                   │  (localhost)  │                       │  Application    │
                                   └───────────────┘                       └─────────────────┘
```

**三个独立进程**:
1. **FastMCP Server** (端口 8000): 暴露 MCP 工具给客户端
2. **Blender Addon** (端口 9876): 在 Blender 内执行命令
3. **Ollama** (端口 11434): 处理自然语言查询

## 2. 核心组件

### 2.1 MCP Server (`src/blender_open_mcp/server.py`, 1044行)

**框架**: FastMCP

**实例化** (line 61):
```python
mcp = FastMCP("blender_open_mcp")
```

**关键特性**:
- **无生命周期管理**（不同于官方版本）
- **每命令新 TCP 连接**: `_send_blender_command()` 为每个命令创建新 socket
- **异步工具函数**: 所有工具都是 `async` 的
- **Pydantic v2 输入验证**: 所有工具参数都有类型验证
- **MCP 工具注解**: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- **运行时可变状态**: `_state` 字典存储 Ollama URL 和模型

**常量** (lines 41-48):
```python
BLENDER_HOST = "localhost"
BLENDER_PORT = 9876
BLENDER_TIMEOUT = 30.0
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"
POLYHAVEN_API_BASE = "https://api.polyhaven.com"
```

### 2.2 Blender Addon (`addon.py`, 655行)

**关键特性**:
- **模块级全局状态**: `_server_socket`, `_server_thread`, `_server_running`
- **HANDLERS 字典分发**: 基于字典的命令路由
- **换行符终止协议**: JSON + `\n`
- **直接执行**（无 `bpy.app.timers.register`）
- **简洁 UI**: 仅 host/port 配置和启动/停止按钮

### 2.3 MCP Client (`client.py`, 497行)

**关键特性**:
- `BlenderMCPClient` 类，异步上下文管理器
- JSON-RPC 2.0 over HTTP
- Session ID 管理
- MCP 初始化握手
- 16 个便捷方法
- 交互式 REPL 模式
- CLI 子命令

## 3. 数据流

```
1. MCP Client 发送 JSON-RPC tools/call 到 MCP Server (HTTP)
2. MCP Server 验证输入 (Pydantic)，调用 _send_blender_command()
3. _send_blender_command() 打开新 TCP socket 到 localhost:9876
4. 发送 {"type": "<command>", "params": {...}}\n
5. Blender addon _handle_client() 读取数据，解析 JSON
6. _dispatch() 在 HANDLERS 字典中查找 handler 并调用
7. handler 执行 bpy 操作
8. 响应 {"status": "ok", "result": ...}\n 发回
9. MCP Server 接收响应，格式化后返回给客户端
```

## 4. 项目结构

```
blender-mcp-community/
├── main.py                              # 入口点 (4行)
├── client.py                            # MCP 客户端 + CLI (497行)
├── addon.py                             # Blender 插件 (655行)
├── pyproject.toml                       # 项目配置
├── src/
│   └── blender_open_mcp/
│       ├── __init__.py                  # 包初始化 (9行)
│       ├── client_entry.py              # CLI 桥接 (13行)
│       └── server.py                    # MCP 服务器 (1044行)
└── tests/
    ├── test_server.py                   # 服务器测试 (311行)
    ├── test_client.py                   # 客户端测试 (312行)
    └── test_addon.py                    # 插件测试 (216行)
```

## 5. CLI 入口点

### 5.1 Server CLI

```bash
blender-mcp [OPTIONS]

Options:
  --host TEXT              监听地址 (默认 0.0.0.0)
  --port INTEGER           监听端口 (默认 8000)
  --blender-host TEXT      Blender 主机 (默认 localhost)
  --blender-port INTEGER   Blender 端口 (默认 9876)
  --ollama-url TEXT        Ollama URL
  --ollama-model TEXT      Ollama 模型 (默认 llama3.2)
  --transport [streamable_http|stdio]  传输协议
```

### 5.2 Client CLI

```bash
blender-mcp-client [COMMAND]

Commands:
  interactive (i, shell)   交互式 REPL
  scene                    获取场景信息
  tools                    列出可用工具
  tool <name> [args]       调用单个工具
  prompt <text>            发送 AI prompt
```

## 6. 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BLENDER_HOST` | `localhost` | Blender addon 主机 |
| `BLENDER_PORT` | `9876` | Blender addon 端口 |
| `DEFAULT_OLLAMA_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `DEFAULT_OLLAMA_MODEL` | `llama3.2` | 默认 Ollama 模型 |

## 7. 与官方版本的架构差异

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 连接模型 | 持久连接 | 每命令新连接 |
| 协议分隔 | 无分隔符 | 换行符 `\n` |
| 线程安全 | `bpy.app.timers.register` | 直接执行 |
| 工具函数 | 同步 | 异步 |
| 输入验证 | 无 | Pydantic v2 |
| 测试 | 无 | 839 行测试 |
| 客户端 | 无 | 完整客户端库 |
| 外部集成 | PolyHaven, Sketchfab, Hyper3D, Hunyuan3D | PolyHaven, Ollama |
