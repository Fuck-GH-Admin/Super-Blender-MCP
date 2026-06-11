# Blender MCP Community - 客户端与 CLI

## 1. BlenderMCPClient 类

**文件**: `client.py` (497行)

### 1.1 基本用法

```python
async with BlenderMCPClient("http://localhost:8000") as client:
    scene_info = await client.get_scene_info()
    await client.create_object("CUBE", name="MyCube", location={"x": 1, "y": 2, "z": 3})
```

### 1.2 构造函数 (lines 41-70)

```python
class BlenderMCPClient:
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id = None
        self._http = httpx.AsyncClient(timeout=timeout)
```

### 1.3 异步上下文管理器

```python
async def __aenter__(self):
    await self._initialize()
    return self

async def __aexit__(self, *args):
    await self._http.aclose()
```

### 1.4 MCP 协议方法

**`_post(payload)`** (lines 73-122):
- 发送 JSON-RPC 到 `{base_url}/mcp`
- 处理 Session ID (`Mcp-Session-Id` header)
- 解析换行分隔的 JSON 和 SSE 风格 `data:` 前缀
- 处理 202 Accepted 响应

**`_initialize()`** (lines 124-142):
```python
async def _initialize(self):
    result = await self._post({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "blender-mcp-client", "version": "1.0.0"}
        }
    })
    await self._notify("notifications/initialized", {})
    return result
```

**`_notify(method, params)`** (lines 144-155):
- 发送单向通知（无响应）

**`call_tool(tool_name, arguments)`** (lines 157-178):
```python
async def call_tool(self, tool_name: str, arguments: dict = None) -> str:
    result = await self._post({
        "jsonrpc": "2.0",
        "id": self._next_id(),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}}
    })
    # 从 content blocks 提取文本
    content = result.get("content", [])
    return "\n".join(block.get("text", "") for block in content if block.get("type") == "text")
```

**`list_tools()`** (lines 180-184):
```python
async def list_tools(self) -> list:
    result = await self._post({
        "jsonrpc": "2.0",
        "id": self._next_id(),
        "method": "tools/list",
        "params": {}
    })
    return result.get("tools", [])
```

### 1.5 便捷方法 (lines 190-322)

| 方法 | 参数 | 对应工具 |
|------|------|----------|
| `get_scene_info()` | - | `blender_get_scene_info` |
| `get_object_info(object_name, response_format)` | name, format | `blender_get_object_info` |
| `create_object(primitive_type, name, location, rotation, scale)` | type, name, loc, rot, scale | `blender_create_object` |
| `modify_object(name, location, rotation, scale, visible)` | name, loc, rot, scale, vis | `blender_modify_object` |
| `delete_object(name)` | name | `blender_delete_object` |
| `set_material(object_name, material_name, color)` | obj, mat, color | `blender_set_material` |
| `render_image(file_path)` | path | `blender_render_image` |
| `execute_code(code)` | code | `blender_execute_code` |
| `ai_prompt(prompt, system_prompt)` | prompt, system | `blender_ai_prompt` |
| `get_polyhaven_categories(asset_type)` | type | `blender_get_polyhaven_categories` |
| `search_polyhaven_assets(asset_type, categories, limit, offset)` | type, cats, limit, offset | `blender_search_polyhaven_assets` |
| `download_polyhaven_asset(asset_id, asset_type, resolution, file_format)` | id, type, res, fmt | `blender_download_polyhaven_asset` |
| `set_texture(object_name, texture_id)` | obj, tex | `blender_set_texture` |
| `get_ollama_models()` | - | `blender_get_ollama_models` |
| `set_ollama_model(model_name)` | model | `blender_set_ollama_model` |
| `set_ollama_url(url)` | url | `blender_set_ollama_url` |

### 1.6 异常类

```python
class MCPError(Exception):
    """MCP 协议错误"""
```

---

## 2. CLI 接口

### 2.1 入口点

```bash
blender-mcp-client [COMMAND] [OPTIONS]
```

### 2.2 子命令

#### `interactive` (别名: `i`, `shell`)

**功能**: 交互式 REPL

**选项**: `--host`, `--timeout`

**命令**:
| 命令 | 说明 |
|------|------|
| `scene` | 获取场景信息 |
| `object <name>` | 获取对象信息 |
| `create <type> [name]` | 创建基本体 |
| `delete <name>` | 删除对象 |
| `material <obj> <mat> [color]` | 设置材质 |
| `render <path>` | 渲染图像 |
| `exec <code>` | 执行代码 |
| `prompt <text>` | AI 提示 |
| `models` | 列出 Ollama 模型 |
| `model <name>` | 设置 Ollama 模型 |
| `polyhaven cats [type]` | PolyHaven 分类 |
| `polyhaven search [type]` | 搜索 PolyHaven |
| `tools` | 列出可用工具 |
| `help` | 显示帮助 |
| `quit` | 退出 |

#### `scene`

**功能**: 获取场景信息（一次性）

#### `tools`

**功能**: 列出所有可用工具

#### `tool <name> [args...]`

**功能**: 调用单个工具

**示例**:
```bash
blender-mcp-client tool blender_get_scene_info
blender-mcp-client tool blender_create_object '{"primitive_type": "CUBE", "name": "MyCube"}'
```

#### `prompt <text>`

**功能**: 发送 AI prompt

**选项**: `--system-prompt`

### 2.3 通用选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `http://localhost:8000` | MCP Server URL |
| `--timeout` | `60.0` | 请求超时（秒） |

---

## 3. Server CLI

### 3.1 入口点

```bash
blender-mcp [OPTIONS]
```

### 3.2 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8000` | 监听端口 |
| `--blender-host` | `localhost` | Blender 主机 |
| `--blender-port` | `9876` | Blender 端口 |
| `--ollama-url` | `http://localhost:11434` | Ollama URL |
| `--ollama-model` | `llama3.2` | Ollama 模型 |
| `--transport` | `streamable_http` | 传输协议 (streamable_http/stdio) |

### 3.3 传输模式

**streamable_http** (默认):
- HTTP 服务器
- 端点: `/mcp`
- 支持 Session ID

**stdio**:
- 标准输入/输出
- 适用于 Claude Desktop, Cursor
- 配置示例:
```json
{
    "mcpServers": {
        "blender": {
            "command": "blender-mcp",
            "args": ["--transport", "stdio"]
        }
    }
}
```

---

## 4. Python API 使用示例

```python
import asyncio
from client import BlenderMCPClient

async def main():
    async with BlenderMCPClient("http://localhost:8000") as client:
        # 获取场景信息
        scene = await client.get_scene_info()
        print(scene)

        # 创建对象
        await client.create_object(
            primitive_type="SPHERE",
            name="MySphere",
            location={"x": 0, "y": 0, "z": 1}
        )

        # 设置材质
        await client.set_material(
            object_name="MySphere",
            material_name="RedMaterial",
            color=[1.0, 0.0, 0.0]
        )

        # 渲染
        await client.render_image("/tmp/render.png")

asyncio.run(main())
```

---

## 5. 与官方版本的客户端差异

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 客户端库 | 无 | BlenderMCPClient 类 |
| CLI | 无 | 完整 CLI (REPL + 一次性命令) |
| 类型安全 | 无 | 类型化便捷方法 |
| 会话管理 | 无 | Session ID 跟踪 |
| 异步支持 | 无 | 完全异步 |
| 错误处理 | 无 | MCPError 异常类 |
