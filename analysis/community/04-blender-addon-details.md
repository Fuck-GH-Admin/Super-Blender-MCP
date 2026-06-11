# Blender MCP Community - Blender 插件详解

> 源码: `addon.py` (655行)

## 1. 插件元数据

```python
bl_info = {
    "name": "Blender MCP",
    "version": (2, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Blender MCP",
    "description": "Connect Blender to MCP server for AI-assisted 3D modeling",
    "category": "Development",
}
```

## 2. 协议规范

**请求格式**:
```json
{"type": "<command>", "params": {...}}
```

**响应格式**:
```json
{"status": "ok", "result": <any>}
{"status": "error", "message": "<reason>"}
```

**传输**: TCP socket，换行符终止

## 3. 全局状态

```python
_server_socket = None    # 服务器 socket
_server_thread = None    # 服务器线程
_server_running = False  # 运行标志
```

## 4. 辅助函数

### 4.1 响应格式化 (lines 58-63)

```python
def _ok(result):
    return {"status": "ok", "result": result}

def _err(message):
    return {"status": "error", "message": message}
```

### 4.2 向量转换 (lines 65-76)

```python
def vec3_from_list(data, default=(0, 0, 0)):
    """从列表或字典提取 [x, y, z]"""
    if isinstance(data, dict):
        return (data.get("x", default[0]), data.get("y", default[1]), data.get("z", default[2]))
    if isinstance(data, (list, tuple)) and len(data) >= 3:
        return tuple(data[:3])
    return default
```

## 5. TCP 服务器 (lines 46-516)

### 5.1 启动服务器 (`_server_loop`, lines 492-516)

```python
def _server_loop(host, port):
    global _server_socket, _server_running
    _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_socket.settimeout(1.0)  # 1秒超时用于优雅关闭
    _server_socket.bind((host, port))
    _server_socket.listen(5)

    while _server_running:
        try:
            conn, addr = _server_socket.accept()
            thread = threading.Thread(target=_handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
        except socket.timeout:
            continue
```

### 5.2 客户端处理 (`_handle_client`, lines 465-489)

```python
def _handle_client(conn, addr):
    try:
        data = b""
        while True:
            chunk = conn.recv(8192)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break  # 收到换行符，消息完整

        request = json.loads(data.decode("utf-8").strip())
        response = _dispatch(request.get("type"), request.get("params", {}))
        conn.sendall(json.dumps(response).encode("utf-8") + b"\n")
    except Exception as e:
        conn.sendall(json.dumps(_err(str(e))).encode("utf-8") + b"\n")
    finally:
        conn.close()
```

### 5.3 命令分发 (`_dispatch`, lines 451-462)

```python
def _dispatch(command_type, params):
    handler = HANDLERS.get(command_type)
    if not handler:
        return _err(f"Unknown command: {command_type}")
    try:
        return _ok(handler(params))
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")
```

## 6. Handler 函数 (15个)

### 6.1 `handle_get_scene_info` (line 76)

**返回**:
```python
{
    "scene_name": str,
    "frame_start": int,
    "frame_end": int,
    "render_engine": str,
    "resolution_x": int,
    "resolution_y": int,
    "camera": str or None,
    "objects": [
        {
            "name": str,
            "type": str,
            "location": [x, y, z],
            "rotation": [x, y, z],
            "scale": [x, y, z],
            "visible": bool,
            "material_slots": [str, ...]
        },
        ...
    ]
}
```

**特性**: 返回所有对象（无数量限制）

### 6.2 `handle_get_object_info` (line 104)

**返回**:
```python
{
    "name": str,
    "type": str,
    "location": [x, y, z],
    "rotation_degrees": [x, y, z],
    "rotation_radians": [x, y, z],
    "scale": [x, y, z],
    "visible": bool,
    "parent": str or None,
    "children": [str, ...],
    # MESH 类型额外:
    "vertex_count": int,
    "edge_count": int,
    "polygon_count": int,
    # LIGHT 类型额外:
    "light_type": str,
    "energy": float,
    "color": [r, g, b],
    # CAMERA 类型额外:
    "camera_type": str,
    "focal_length": float
}
```

### 6.3 `handle_create_object` (line 136)

**支持的基本体** (10种):
```python
PRIMITIVES = {
    "CUBE": bpy.ops.mesh.primitive_cube_add,
    "SPHERE": bpy.ops.mesh.primitive_uv_sphere_add,
    "CYLINDER": bpy.ops.mesh.primitive_cylinder_add,
    "CONE": bpy.ops.mesh.primitive_cone_add,
    "TORUS": bpy.ops.mesh.primitive_torus_add,
    "PLANE": bpy.ops.mesh.primitive_plane_add,
    "CIRCLE": bpy.ops.mesh.primitive_circle_add,
    "ICO_SPHERE": bpy.ops.mesh.primitive_ico_sphere_add,
    "GRID": bpy.ops.mesh.primitive_grid_add,
    "MONKEY": bpy.ops.mesh.primitive_monkey_add,
}
```

**流程**:
1. 验证基本体类型
2. 调用 `bpy.ops.mesh.primitive_*_add()`
3. 设置 location, rotation, scale
4. 可选重命名对象和数据

### 6.4 `handle_modify_object` (line 184)

**功能**: 部分更新对象属性
- location
- rotation_euler
- scale
- hide_viewport

**返回**: 仅返回修改的字段

### 6.5 `handle_delete_object` (line 215)

```python
bpy.data.objects.remove(obj, do_unlink=True)
```

### 6.6 `handle_set_material` (line 224)

**流程**:
1. 查找或创建材质 (`use_nodes=True`)
2. 查找或创建 Principled BSDF 节点
3. 设置 Base Color (如果提供)
4. 分配到对象的第一个材质槽

### 6.7 `handle_render_image` (line 264)

```python
scene.render.filepath = file_path
bpy.ops.render.render(write_still=True)
```

### 6.8 `handle_execute_blender_code` (line 277)

```python
old_stdout = sys.stdout
sys.stdout = buffer = io.StringIO()
try:
    exec(compile(code, "<blender_mcp>", "exec"), {"bpy": bpy})
    output = buffer.getvalue()
    return {"output": output or "Code executed successfully"}
except Exception:
    return {"output": traceback.format_exc()}
finally:
    sys.stdout = old_stdout
```

### 6.9 PolyHaven Handler

**`handle_get_polyhaven_categories`** (line 300):
- 使用 `urllib.request.urlopen`
- 直接调用 PolyHaven API

**`handle_search_polyhaven_assets`** (line 307):
- 返回 total_count + 前 50 个资产 ID

**`handle_download_polyhaven_asset`** (line 319):
- 解析下载 URL
- 下载到 `bpy.app.tempdir`
- HDRI: 创建 Environment Texture 节点
- 纹理/模型: 返回文件路径

**`handle_set_texture`** (line 374):
- 查找下载的纹理文件
- 创建 Image Texture -> Principled BSDF -> Material Output 节点图
- 分配到对象

### 6.10 Ollama Handler

**`handle_set_ollama_model`** (line 415): 确认响应（状态由 server 管理）

**`handle_set_ollama_url`** (line 420): 确认响应

**`handle_get_ollama_models`** (line 424): 信息性说明

## 7. HANDLERS 注册字典 (lines 432-448)

```python
HANDLERS = {
    "get_scene_info": handle_get_scene_info,
    "get_object_info": handle_get_object_info,
    "create_object": handle_create_object,
    "modify_object": handle_modify_object,
    "delete_object": handle_delete_object,
    "set_material": handle_set_material,
    "render_image": handle_render_image,
    "execute_blender_code": handle_execute_blender_code,
    "get_polyhaven_categories": handle_get_polyhaven_categories,
    "search_polyhaven_assets": handle_search_polyhaven_assets,
    "download_polyhaven_asset": handle_download_polyhaven_asset,
    "set_texture": handle_set_texture,
    "set_ollama_model": handle_set_ollama_model,
    "set_ollama_url": handle_set_ollama_url,
    "get_ollama_models": handle_get_ollama_models,
}
```

## 8. UI 组件

### 8.1 Operators

**`BLENDER_MCP_OT_StartServer`** (line 523):
```python
def execute(self, context):
    global _server_thread, _server_running
    _server_running = True
    props = context.scene.blender_mcp_props
    _server_thread = threading.Thread(target=_server_loop, args=(props.server_host, props.server_port))
    _server_thread.daemon = True
    _server_thread.start()
```

**`BLENDER_MCP_OT_StopServer`** (line 547):
```python
def execute(self, context):
    global _server_running
    _server_running = False
```

### 8.2 PropertyGroup (line 571)

```python
class BlenderMCPProperties(bpy.types.PropertyGroup):
    server_host: StringProperty(name="Host", default="localhost")
    server_port: IntProperty(name="Port", default=9876, min=1024, max=65535)
```

### 8.3 面板 (`BLENDER_MCP_PT_Panel`, line 590)

**位置**: `View3D > Sidebar > Blender MCP`

**内容**:
- Host 输入框
- Port 输入框
- Start Server 按钮
- Stop Server 按钮
- Quick Reference 信息框（端口号 8000, 9876, 11434）

## 9. 注册 (lines 637-650)

```python
def register():
    bpy.utils.register_class(BLENDERMCPProperties)
    bpy.utils.register_class(BLENDER_MCP_OT_StartServer)
    bpy.utils.register_class(BLENDER_MCP_OT_StopServer)
    bpy.utils.register_class(BLENDER_MCP_PT_Panel)
    bpy.types.Scene.blender_mcp_props = PointerProperty(type=BlenderMCPProperties)

def unregister():
    bpy.utils.unregister_class(BLENDER_MCP_PT_Panel)
    bpy.utils.unregister_class(BLENDER_MCP_OT_StopServer)
    bpy.utils.unregister_class(BLENDER_MCP_OT_StartServer)
    bpy.utils.unregister_class(BLENDERMCPProperties)
    del bpy.types.Scene.blender_mcp_props
```

## 10. 与官方版本的插件差异

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 代码行数 | 2636 | 655 |
| 架构 | BlenderMCPServer 类 | 模块级函数 |
| 命令执行 | `bpy.app.timers.register` | 直接调用 |
| Handler 注册 | 条件注册 | 固定字典 |
| UI 面板 | 完整配置 | 仅 host/port |
| 场景信息 | 限制 10 个对象 | 全部对象 |
| 对象信息 | 无 light/camera 数据 | 包含 light/camera 数据 |
| 纹理设置 | 完整 PBR 节点图 | 简单单贴图 |
| PolyHaven UI | 开关 + API 密钥 | 无 |
| 遥测 UI | 同意开关 | 无 |
