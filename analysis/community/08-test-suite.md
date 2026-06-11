# Blender MCP Community - 测试套件

> 总计 839 行测试代码

## 1. 测试概览

| 文件 | 行数 | 测试数 | 覆盖范围 |
|------|------|--------|----------|
| `test_server.py` | 311 | 23 | 输入模型、错误处理、工具注解、PolyHaven |
| `test_client.py` | 312 | 16 | 客户端构造、工具调用、便捷方法、会话 |
| `test_addon.py` | 216 | 19 | Handler、分发、PolyHaven |

---

## 2. test_server.py (311行)

### 2.1 TestInputModels (8个测试)

**Vec3 测试**:
```python
def test_vec3_defaults():
    v = Vec3()
    assert v.x == 0.0 and v.y == 0.0 and v.z == 0.0

def test_vec3_custom():
    v = Vec3(x=1.0, y=2.0, z=3.0)
    assert v.as_list() == [1.0, 2.0, 3.0]
```

**SetMaterialInput 颜色验证**:
```python
def test_valid_color():
    m = SetMaterialInput(object_name="obj", material_name="mat", color=[1.0, 0.5, 0.0])
    assert m.color == [1.0, 0.5, 0.0, 1.0]  # 自动添加 alpha

def test_auto_alpha():
    m = SetMaterialInput(object_name="obj", material_name="mat", color=[0.1, 0.2, 0.3])
    assert m.color[3] == 1.0

def test_out_of_range():
    with pytest.raises(ValidationError):
        SetMaterialInput(object_name="obj", material_name="mat", color=[1.5, 0.0, 0.0])

def test_wrong_length():
    with pytest.raises(ValidationError):
        SetMaterialInput(object_name="obj", material_name="mat", color=[1.0, 0.0])
```

**CreateObjectInput 测试**:
```python
def test_defaults():
    c = CreateObjectInput(primitive_type="CUBE")
    assert c.name == ""
    assert c.location.as_list() == [0.0, 0.0, 0.0]
    assert c.scale.as_list() == [1.0, 1.0, 1.0]
```

**GetObjectInfoInput 测试**:
```python
def test_empty_name():
    with pytest.raises(ValidationError):
        GetObjectInfoInput(object_name="")
```

**SearchPolyHavenInput 测试**:
```python
def test_pagination_defaults():
    s = SearchPolyHavenInput()
    assert s.limit == 20
    assert s.offset == 0

def test_pagination_bounds():
    with pytest.raises(ValidationError):
        SearchPolyHavenInput(limit=0)  # min=1
    with pytest.raises(ValidationError):
        SearchPolyHavenInput(limit=101)  # max=100
```

### 2.2 TestErrorHandling (3个测试)

```python
def test_connection_refused():
    msg = _handle_blender_error(ConnectionRefusedError())
    assert "not running" in msg.lower()

def test_timeout():
    msg = _handle_blender_error(TimeoutError())
    assert "too long" in msg.lower()

def test_runtime_error():
    msg = _handle_blender_error(RuntimeError("test error"))
    assert "test error" in msg
```

### 2.3 TestBlenderCommandHelper (3个测试)

```python
def test_connection_refused_on_unused_port():
    with pytest.raises(ConnectionRefusedError):
        _send_blender_command("test", {}, host="localhost", port=1)  # 未使用端口

def test_format_ok():
    result = _format_blender_result({"status": "ok", "result": {"key": "value"}})
    assert "key" in result

def test_format_error():
    result = _format_blender_result({"status": "error", "message": "test error"})
    assert "test error" in result
```

### 2.4 TestOllamaIntegration (4个测试，全部 mock)

```python
@pytest.mark.asyncio
async def test_query_ollama_success(mock_httpx):
    mock_httpx.post.return_value = MockResponse({"response": "Hello"})
    result = await _query_ollama("test prompt")
    assert result == "Hello"

@pytest.mark.asyncio
async def test_query_ollama_connection_error(mock_httpx):
    mock_httpx.post.side_effect = httpx.ConnectError("refused")
    with pytest.raises(Exception):
        await _query_ollama("test prompt")

def test_set_ollama_model():
    _state["ollama_model"] = "old"
    # 调用工具后检查状态
    assert _state["ollama_model"] == "new_model"

def test_set_ollama_url():
    _state["ollama_url"] = "http://old:11434"
    # 调用工具后检查状态
    assert _state["ollama_url"] == "http://new:11434"
```

### 2.5 TestToolAnnotations (3个测试)

```python
def test_delete_is_destructive():
    # 检查 blender_delete_object 的 annotations
    assert annotations["destructiveHint"] is True

def test_scene_info_is_read_only():
    # 检查 blender_get_scene_info 的 annotations
    assert annotations["readOnlyHint"] is True

def test_execute_code_is_destructive():
    # 检查 blender_execute_code 的 annotations
    assert annotations["destructiveHint"] is True
```

### 2.6 TestPolyHavenTools (2个测试，mock HTTP)

```python
@pytest.mark.asyncio
async def test_get_categories(mock_httpx):
    mock_httpx.get.return_value = MockResponse({"hdris": ["nature", "urban"]})
    result = await blender_get_polyhaven_categories(GetPolyHavenCategoriesInput())
    assert "nature" in result

@pytest.mark.asyncio
async def test_search_pagination(mock_httpx):
    mock_httpx.get.return_value = MockResponse({"assets": {f"asset_{i}": {} for i in range(50)}})
    result = await blender_search_polyhaven_assets(SearchPolyHavenInput(limit=10, offset=5))
    # 验证分页参数传递正确
```

---

## 3. test_client.py (312行)

### 3.1 TestClientConstruction (3个测试)

```python
def test_default_url():
    c = BlenderMCPClient()
    assert c.base_url == "http://localhost:8000"

def test_trailing_slash():
    c = BlenderMCPClient("http://localhost:8000/")
    assert c.base_url == "http://localhost:8000"

def test_default_timeout():
    c = BlenderMCPClient()
    assert c.timeout == 60.0
```

### 3.2 TestCallTool (3个测试，mock HTTP)

```python
@pytest.mark.asyncio
async def test_success(mock_httpx):
    mock_httpx.post.return_value = MockResponse({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": "ok"}]}
    })
    async with BlenderMCPClient() as client:
        result = await client.call_tool("test_tool")
        assert result == "ok"

@pytest.mark.asyncio
async def test_mcp_error(mock_httpx):
    mock_httpx.post.return_value = MockResponse({
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -1, "message": "tool not found"}
    })
    with pytest.raises(MCPError):
        async with BlenderMCPClient() as client:
            await client.call_tool("nonexistent")

@pytest.mark.asyncio
async def test_connection_error(mock_httpx):
    mock_httpx.post.side_effect = httpx.ConnectError("refused")
    with pytest.raises(httpx.ConnectError):
        async with BlenderMCPClient() as client:
            await client.call_tool("test")
```

### 3.3 TestConvenienceMethods (5个测试，mock call_tool)

```python
@pytest.mark.asyncio
async def test_create_object(mock_call_tool):
    await client.create_object("CUBE", name="MyCube", location={"x": 1, "y": 2, "z": 3})
    mock_call_tool.assert_called_with("blender_create_object", {
        "primitive_type": "CUBE",
        "name": "MyCube",
        "location": {"x": 1, "y": 2, "z": 3},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 1, "y": 1, "z": 1}
    })

@pytest.mark.asyncio
async def test_set_material_with_color(mock_call_tool):
    await client.set_material("obj", "mat", [1.0, 0.0, 0.0])
    mock_call_tool.assert_called_with("blender_set_material", {
        "object_name": "obj",
        "material_name": "mat",
        "color": [1.0, 0.0, 0.0]
    })

@pytest.mark.asyncio
async def test_modify_object_partial(mock_call_tool):
    await client.modify_object("obj", location={"x": 1, "y": 0, "z": 0})
    call_args = mock_call_tool.call_args[0][1]
    assert "location" in call_args
    assert "rotation" not in call_args  # 部分更新

@pytest.mark.asyncio
async def test_ai_prompt_with_system(mock_call_tool):
    await client.ai_prompt("test", system_prompt="custom system")
    mock_call_tool.assert_called_with("blender_ai_prompt", {
        "prompt": "test",
        "system_prompt": "custom system"
    })

@pytest.mark.asyncio
async def test_search_defaults(mock_call_tool):
    await client.search_polyhaven_assets()
    mock_call_tool.assert_called_with("blender_search_polyhaven_assets", {
        "asset_type": "all",
        "categories": None,
        "limit": 20,
        "offset": 0
    })
```

### 3.4 TestListTools (1个测试)

```python
@pytest.mark.asyncio
async def test_list_tools(mock_httpx):
    mock_httpx.post.return_value = MockResponse({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "tool1"}, {"name": "tool2"}]}
    })
    async with BlenderMCPClient() as client:
        tools = await client.list_tools()
        assert len(tools) == 2
```

### 3.5 TestSessionHandling (1个测试)

```python
@pytest.mark.asyncio
async def test_session_id(mock_httpx):
    mock_httpx.post.return_value = MockResponse(
        {"jsonrpc": "2.0", "id": 1, "result": {...}},
        headers={"Mcp-Session-Id": "test-session-123"}
    )
    async with BlenderMCPClient() as client:
        assert client.session_id == "test-session-123"
```

---

## 4. test_addon.py (216行)

### 4.1 Mock bpy 模块

```python
# 完全模拟 bpy 模块
import sys
from unittest.mock import MagicMock

bpy = MagicMock()
sys.modules["bpy"] = bpy
```

### 4.2 TestAddonHandlers (11个测试)

```python
def test_scene_info_empty():
    bpy.context.scene.objects = []
    result = handle_get_scene_info({})
    assert result["objects"] == []

def test_object_info_not_found():
    bpy.data.objects = {}  # 空字典
    with pytest.raises(KeyError):
        handle_get_object_info({"object_name": "nonexistent"})

def test_create_object_invalid_type():
    with pytest.raises(ValueError):
        handle_create_object({"primitive_type": "INVALID"})

def test_delete_not_found():
    bpy.data.objects = {}
    with pytest.raises(KeyError):
        handle_delete_object({"name": "nonexistent"})

def test_modify_not_found():
    bpy.data.objects = {}
    with pytest.raises(KeyError):
        handle_modify_object({"name": "nonexistent"})

def test_set_material_not_found():
    bpy.data.objects = {}
    with pytest.raises(KeyError):
        handle_set_material({"object_name": "nonexistent", "material_name": "mat"})

def test_set_material_unsupported_type():
    # 非 MESH 对象
    mock_obj = MagicMock()
    mock_obj.type = "CAMERA"
    bpy.data.objects = {"cam": mock_obj}
    with pytest.raises(TypeError):
        handle_set_material({"object_name": "cam", "material_name": "mat"})

def test_vec3_from_list():
    assert vec3_from_list([1, 2, 3]) == (1, 2, 3)
    assert vec3_from_list({"x": 1, "y": 2, "z": 3}) == (1, 2, 3)
    assert vec3_from_list(None) == (0, 0, 0)

def test_ok_response():
    assert _ok({"key": "value"}) == {"status": "ok", "result": {"key": "value"}}

def test_err_response():
    assert _err("test") == {"status": "error", "message": "test"}

def test_all_handlers_registered():
    assert len(HANDLERS) == 15
    assert "get_scene_info" in HANDLERS
    assert "execute_blender_code" in HANDLERS
```

### 4.3 TestAddonDispatch (3个测试)

```python
def test_unknown_command():
    result = _dispatch("unknown_command", {})
    assert result["status"] == "error"
    assert "Unknown command" in result["message"]

def test_valid_command():
    bpy.context.scene.objects = []
    result = _dispatch("get_scene_info", {})
    assert result["status"] == "ok"

def test_handler_exception():
    bpy.data.objects = {}
    result = _dispatch("get_object_info", {"object_name": "nonexistent"})
    assert result["status"] == "error"
```

### 4.4 TestAddonPolyHaven (2个测试，mock urllib)

```python
def test_get_categories(mock_urlopen):
    mock_urlopen.return_value.read.return_value = b'{"hdris": ["nature"]}'
    result = handle_get_polyhaven_categories({"asset_type": "hdris"})
    assert "hdris" in result

def test_search_assets(mock_urlopen):
    mock_urlopen.return_value.read.return_value = b'{"assets": {"a1": {}, "a2": {}}}'
    result = handle_search_polyhaven_assets({"asset_type": "all"})
    assert result["total_count"] == 2
```

---

## 5. 测试运行

### 5.1 运行所有测试

```bash
pytest tests/
```

### 5.2 运行特定文件

```bash
pytest tests/test_server.py
pytest tests/test_client.py
pytest tests/test_addon.py
```

### 5.3 运行特定测试

```bash
pytest tests/test_server.py::TestInputModels::test_vec3_defaults
```

### 5.4 带输出运行

```bash
pytest -v tests/
```

---

## 6. 测试覆盖率

测试覆盖了:
- 输入验证 (Pydantic 模型)
- 错误处理
- 工具注解
- PolyHaven 集成
- Ollama 集成
- 客户端构造和方法
- Addon handler 和分发

**未覆盖**:
- 实际 Blender API 调用（需要 Blender 环境）
- TCP 网络通信（需要启动服务器）
- 端到端集成测试

---

## 7. 与官方版本的测试差异

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 测试文件 | 无 | 3 个文件 |
| 测试行数 | 0 | 839 |
| 测试数 | 0 | 58 |
| 覆盖范围 | 无 | 输入、错误、工具、handler |
| Mock 策略 | 无 | bpy、HTTP、socket |
| 异步测试 | 无 | pytest-asyncio |
