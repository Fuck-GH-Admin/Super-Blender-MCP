# Blender MCP Community - 通信协议

## 1. 概述

系统有三个独立的通信通道:
1. MCP Server <-> Blender Addon (TCP Socket)
2. MCP Client <-> MCP Server (HTTP JSON-RPC)
3. MCP Server <-> Ollama (HTTP)

---

## 2. MCP Server <-> Blender Addon (TCP)

### 2.1 传输层

- **协议**: 原始 TCP Socket
- **默认端口**: 9876
- **连接模式**: 每命令新连接（非持久）
- **分隔符**: 换行符 `\n`
- **超时**: 30 秒 (`BLENDER_TIMEOUT`)

### 2.2 消息格式

**请求**:
```json
{"type": "<command_type>", "params": {...}}\n
```

**成功响应**:
```json
{"status": "ok", "result": <data>}\n
```

**错误响应**:
```json
{"status": "error", "message": "<error_reason>"}\n
```

### 2.3 发送逻辑 (`_send_blender_command()`, server.py lines 68-109)

```python
def _send_blender_command(command_type: str, params: dict = None) -> dict:
    # 1. 创建新 TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(BLENDER_TIMEOUT)

    # 2. 连接
    sock.connect((BLENDER_HOST, BLENDER_PORT))

    # 3. 构造并发送请求
    payload = json.dumps({"type": command_type, "params": params or {}}) + "\n"
    sock.sendall(payload.encode("utf-8"))

    # 4. 接收响应（读到连接关闭）
    chunks = []
    while True:
        try:
            data = sock.recv(8192)
            if not data:
                break
            chunks.append(data)
        except socket.timeout:
            break

    # 5. 解析响应
    response = json.loads(b"".join(chunks).decode("utf-8"))
    return response
```

### 2.4 接收逻辑

- **读到连接关闭**: 持续 `recv(8192)` 直到返回空数据
- **8192 字节缓冲区**
- **30 秒超时**: 如果超时，尝试解析已接收的数据
- **无换行符检查**: 不依赖换行符作为消息边界

### 2.5 错误处理

| 异常 | 处理 |
|------|------|
| `ConnectionRefusedError` | "Blender is not running or the add-on server is not started" |
| `TimeoutError` | "Blender took too long to respond" |
| `RuntimeError` | "Unexpected error: {error}" |

---

## 3. MCP Client <-> MCP Server (HTTP JSON-RPC)

### 3.1 传输层

- **协议**: MCP over Streamable HTTP (JSON-RPC 2.0)
- **默认端点**: `http://localhost:8000/mcp`
- **Session 管理**: 通过 `Mcp-Session-Id` header
- **响应格式**: 换行分隔的 JSON 或 SSE 风格 `data:` 前缀

### 3.2 初始化握手

```
Client -> Server: {"method": "initialize", "params": {"protocolVersion": "2024-11-05", ...}}
Server -> Client: {"result": {"protocolVersion": "2024-11-05", "sessionId": "..."}}
Client -> Server: {"method": "notifications/initialized"}
```

### 3.3 工具调用

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "blender_get_scene_info",
        "arguments": {}
    }
}
```

### 3.4 Session 管理

```python
# 从响应 header 获取 session ID
session_id = response.headers.get("Mcp-Session-Id")

# 后续请求携带 session ID
headers["Mcp-Session-Id"] = session_id
```

---

## 4. MCP Server <-> Ollama (HTTP)

### 4.1 端点

```
POST http://localhost:11434/api/generate
```

### 4.2 请求格式

```json
{
    "model": "llama3.2",
    "prompt": "<user prompt>",
    "system": "<system prompt>",
    "stream": false
}
```

### 4.3 响应格式

```json
{
    "response": "<generated text>"
}
```

### 4.4 实现细节

- 使用 `httpx.AsyncClient`
- 60 秒超时
- `stream=False`（非流式）
- 可配置 URL 和模型

---

## 5. 协议流程图

### 5.1 完整请求流程

```
MCP Client          MCP Server          Blender Addon
    │                    │                    │
    │── HTTP POST ──────>│                    │
    │   (JSON-RPC)       │                    │
    │                    │── TCP Connect ────>│
    │                    │── {"type":"cmd"} ─>│
    │                    │                    │── 解析 JSON
    │                    │                    │── 调用 handler
    │                    │                    │── 构造响应
    │                    │<── {"status":"ok"} ─│
    │                    │── TCP Close ──────>│
    │<── JSON-RPC ──────│                    │
    │   (result)         │                    │
```

### 5.2 Ollama 集成流程

```
MCP Client          MCP Server            Ollama
    │                    │                    │
    │── tools/call ─────>│                    │
    │   (ai_prompt)      │                    │
    │                    │── HTTP POST ──────>│
    │                    │   /api/generate     │
    │                    │<── response ───────│
    │<── result ─────────│                    │
```

---

## 6. 超时配置

| 位置 | 超时值 | 说明 |
|------|--------|------|
| Server -> Blender | 30秒 | TCP socket 超时 |
| Server -> Ollama | 60秒 | HTTP 请求超时 |
| Client -> Server | 60秒 | HTTP 请求超时 |

---

## 7. 与官方版本的协议差异

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 消息分隔 | 无分隔符 | 换行符 `\n` |
| 连接模式 | 持久连接 | 每命令新连接 |
| 接收方式 | 累积并尝试 JSON 解析 | 读到连接关闭 |
| 超时时间 | 180秒 | 30秒 |
| 响应状态 | `success` / `error` | `ok` / `error` |
| 外部通信 | Supabase (遥测) | Ollama (AI) |
