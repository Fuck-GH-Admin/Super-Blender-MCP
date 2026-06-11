# Blender MCP Official - 通信协议

## 1. 传输层

- **协议**: 原始 TCP Socket
- **默认端口**: 9876（可通过 UI 或环境变量配置）
- **连接模式**: 持久连接（server 连接一次，复用 socket 发送所有命令）
- **分隔符**: 无换行符分隔，原始 JSON 字节流

## 2. 消息格式

### 请求格式
```json
{"type": "<command_type>", "params": {<key>: <value>, ...}}
```

### 响应格式
```json
// 成功
{"status": "success", "result": {...}}

// 错误
{"status": "error", "message": "<error_description>"}
```

## 3. 连接管理

### 连接建立 (`connect()`, server.py lines 35-48)
```python
def connect(self):
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.socket.connect((self.host, self.port))
```

### 连接验证 (`get_blender_connection()`, lines 219-251)
- 每次获取连接时发送 `get_polyhaven_status` 命令作为 ping
- 如果响应失败，创建新连接
- **注意**: 这是一个有副作用的 ping（会实际执行 PolyHaven 状态检查）

### 连接断开 (`disconnect()`, lines 50-58)
```python
def disconnect(self):
    if self.socket:
        self.socket.close()
        self.socket = None
```

## 4. 数据接收逻辑

### `receive_full_response()` (lines 60-114)

```
1. 设置 socket 超时为 180 秒
2. 循环接收数据:
   a. 尝试 recv(8192) 读取数据块
   b. 累积到 data 缓冲区
   c. 尝试 json.loads(data) 解析
   d. 如果成功解析，返回结果
   e. 如果 recv 超时:
      - 检查累积数据是否为有效 JSON
      - 如果是，返回（降级处理）
      - 如果不是，抛出异常
   f. 如果连接关闭 (recv 返回空):
      - 检查累积数据是否为有效 JSON
      - 如果是，返回
      - 如果不是，抛出异常
```

**关键参数**:
- 缓冲区大小: 8192 字节
- 超时时间: 180 秒
- 错误处理: JSON 解码错误时记录原始数据前 200 字节

## 5. 命令发送逻辑

### `send_command()` (lines 116-169)

```python
def send_command(self, command_type: str, params: dict = None) -> dict:
    # 1. 构造命令
    command = {"type": command_type, "params": params or {}}
    # 2. 序列化为 JSON
    command_json = json.dumps(command)
    # 3. 发送
    self.socket.sendall(command_json.encode('utf-8'))
    # 4. 接收响应
    response = self.receive_full_response()
    # 5. 检查状态
    if response.get('status') == 'error':
        raise Exception(response.get('message', 'Unknown error'))
    return response
```

## 6. 超时配置

| 位置 | 超时值 | 说明 |
|------|--------|------|
| Server `receive_full_response()` | 180秒 | 接收响应的 socket 超时 |
| Server `send_command()` | 180秒 | 发送命令的 socket 超时 |
| Addon `_handle_client` | 无超时 | `client.settimeout(None)` |
| Addon `_server_loop` | 1秒 | accept 轮询超时（用于优雅关闭） |

## 7. 错误处理

### 连接错误
- socket 异常时将 `_blender_connection` 设为 `None`
- 下次调用 `get_blender_connection()` 时自动重连

### JSON 解码错误
- 记录原始响应数据前 200 字节到日志
- 抛出包含原始数据的异常

### 超时错误
- 抛出异常，建议 "try simplifying your request"

### 命令执行错误
- 响应中 `status` 为 `error` 时，抛出包含 `message` 的异常

## 8. 协议流程图

```
Server                          Addon
  │                               │
  │── TCP Connect ───────────────>│
  │                               │
  │── {"type":"cmd","params":{}} >│
  │                               │── 解析 JSON
  │                               │── bpy.app.timers.register()
  │                               │── 主线程执行 handler
  │                               │── 构造响应
  │<── {"status":"success",...} ──│
  │                               │
  │── 下一个命令... ──────────────>│
  │                               │
  │── TCP Disconnect ────────────>│
```

## 9. 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BLENDER_HOST` | `localhost` | 连接目标主机 |
| `BLENDER_PORT` | `9876` | 连接目标端口 |
