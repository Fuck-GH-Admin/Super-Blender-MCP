# Blender MCP Official - Blender 插件详解

> 源码: `addon.py` (2636行)

## 1. 插件元数据

```python
bl_info = {
    "name": "Blender MCP",
    "version": (1, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Connect Blender to Claude via MCP",
}
```

## 2. BlenderMCPServer 类 (lines 39-2321)

### 2.1 构造函数 (lines 40-45)
```python
def __init__(self, host='localhost', port=9876):
    self.host = host
    self.port = port
    self.socket = None
    self.running = False
    self.thread = None
```

### 2.2 服务器启动 (`start()`, lines 47-69)
- 创建 TCP socket，设置 `SO_REUSEADDR`
- 绑定到 host:port
- 开始监听
- 启动守护线程运行 `_server_loop`

### 2.3 服务器停止 (`stop()`, lines 71-91)
- 设置 `running = False`
- 关闭 socket
- 等待线程结束 (join)

### 2.4 服务器主循环 (`_server_loop()`, lines 93-124)
```python
while self.running:
    try:
        client, address = self.socket.accept()  # 1秒超时
        client_thread = threading.Thread(target=self._handle_client, args=(client,))
        client_thread.daemon = True
        client_thread.start()
    except socket.timeout:
        continue
```

### 2.5 客户端处理 (`_handle_client()`, lines 126-184)

**关键架构细节**:
1. 从 socket 读取数据（8192 字节块）
2. 累积到缓冲区，尝试 `json.loads()` 解析
3. 成功解析后，通过 `bpy.app.timers.register(execute_wrapper, first_interval=0.0)` 调度到主线程
4. 等待执行结果（通过共享变量）
5. 将 JSON 响应发回客户端

**线程安全机制**:
```python
# line 170 - 关键: 确保 Blender API 调用在主线程执行
bpy.app.timers.register(execute_wrapper, first_interval=0.0)
```

### 2.6 命令分发 (`_execute_command_internal()`, lines 186-267)

**始终可用的 handler**:
- `get_scene_info`
- `get_object_info`
- `get_viewport_screenshot`
- `execute_code`
- `get_telemetry_consent`
- `get_polyhaven_status`
- `get_hyper3d_status`
- `get_sketchfab_status`
- `get_hunyuan3d_status`

**条件注册的 handler**:
- PolyHaven: `get_polyhaven_categories`, `search_polyhaven_assets`, `download_polyhaven_asset`, `set_texture`
- Hyper3D: `generate_hyper3d_model_text`, `generate_hyper3d_model_image`, `poll_rodin_job`, `import_generated_asset`
- Sketchfab: `search_sketchfab_models`, `get_sketchfab_model_preview`, `download_sketchfab_model`
- Hunyuan3D: `generate_hunyuan3d_model`, `poll_hunyuan_job`, `import_generated_asset_hunyuan`

## 3. Handler 实现

### 3.1 `get_scene_info` (lines 271-303)
- 遍历 `bpy.context.scene.objects[:10]`
- 返回: scene_name, object_count, objects (name/type/location), material_count

### 3.2 `get_object_info` (lines 327-362)
- 通过 `bpy.data.objects[name]` 查找对象
- 返回: type, location, rotation, scale, visibility, materials
- MESH 类型额外: mesh_stats (vertex/edge/polygon count), world_bounding_box

### 3.3 `get_viewport_screenshot` (lines 364-419)
- 查找 3D 视口区域 (`VIEW_3D`)
- 使用 `bpy.ops.screen.screenshot_area()` + `temp_override`
- 可选缩放（如果超过 max_size）
- 保存到临时文件

### 3.4 `execute_code` (lines 421-436)
- 命名空间: `{"bpy": bpy}`
- stdout 重定向到 `io.StringIO`
- 使用 `exec(code, namespace)` 执行
- 捕获输出或异常

### 3.5 PolyHaven Handler (lines 440-806)

**`get_polyhaven_categories`**: GET `https://api.polyhaven.com/categories/{asset_type}`

**`search_polyhaven_assets`**: GET `https://api.polyhaven.com/assets`

**`download_polyhaven_asset`**:
- HDRI: 创建世界节点树
  ```
  TexCoord -> Mapping -> Environment Texture -> Background -> Output World
  ```
- 纹理: 下载所有贴图，创建 Principled BSDF 材质
  - Base Color, Roughness, Metallic, Normal, Displacement, ARM, AO
  - 正确设置颜色空间 (sRGB vs Non-Color)
- 模型: 支持 glTF, FBX, OBJ, blend

**`set_texture`**: 完整 PBR 节点图设置

### 3.6 Hyper3D Rodin Handler (lines 1141-1475)

**双模式支持**:
- MAIN_SITE: `https://hyperhuman.deemos.com/api/v2/rodin`
- FAL_AI: `https://queue.fal.run/fal-ai/hyper3d/rodin`

**工作流**:
1. 创建任务 (text 或 image input)
2. 轮询状态
3. 下载 GLB
4. 通过 `bpy.ops.import_scene.gltf` 导入

### 3.7 Sketchfab Handler (lines 1477-1910)

**API**: `https://api.sketchfab.com/v3`

**认证**: Token (`Authorization: Token {api_key}`)

**下载流程**:
1. 获取下载 URL
2. 下载 ZIP
3. **Zip-slip 安全检查**:
   ```python
   # 防止路径遍历
   if '..' in member.filename or member.filename.startswith('/'):
       continue
   ```
4. glTF 导入
5. 尺寸归一化到 target_size

### 3.8 Hunyuan3D Handler (lines 1912-2321)

**OFFICIAL_API** (腾讯云):
- 签名: TC3-HMAC-SHA256
- Service: "hunyuan", Region: "ap-guangzhou"
- Actions: SubmitHunyuanTo3DJob, QueryHunyuanTo3DJob

**LOCAL_API**:
- 默认端点: `http://localhost:8081/generate`
- 参数: octree_resolution, num_inference_steps, guidance_scale, texture
- 直接返回 GLB

## 4. UI 组件

### 4.1 Addon Preferences (`BLENDERMCP_AddonPreferences`, line 2324)
- 遥测同意开关 (`blendermcp_telemetry_consent`)

### 4.2 侧边栏面板 (`BLENDERMCP_PT_Panel`, line 2359)
- 位置: `View3D > Sidebar > BlenderMCP`
- 端口设置（默认 9876）
- PolyHaven 开关
- Hyper3D Rodin 开关 + 模式选择 + API 密钥
- Sketchfab 开关 + API 密钥
- Hunyuan3D 开关 + 模式选择 + 凭证
- 连接/断开按钮

### 4.3 Operators
- `BLENDERMCP_OT_StartServer` (line 2414): 创建并启动服务器
- `BLENDERMCP_OT_StopServer` (line 2433): 停止并销毁服务器
- `BLENDERMCP_OT_SetFreeTrialHyper3DAPIKey` (line 2403): 设置免费试用密钥
- `BLENDERMCP_OT_OpenTerms` (line 2451): 打开 GitHub 条款页面

## 5. Scene Properties (lines 2469-2588)

| 属性名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `blendermcp_port` | IntProperty | 9876 | 服务器端口 |
| `blendermcp_server_running` | BoolProperty | False | 服务器运行状态 |
| `blendermcp_use_polyhaven` | BoolProperty | False | 启用 PolyHaven |
| `blendermcp_use_hyper3d` | BoolProperty | False | 启用 Hyper3D |
| `blendermcp_hyper3d_mode` | EnumProperty | MAIN_SITE | Hyper3D 模式 |
| `blendermcp_hyper3d_api_key` | StringProperty | - | Hyper3D API 密钥 |
| `blendermcp_use_sketchfab` | BoolProperty | False | 启用 Sketchfab |
| `blendermcp_sketchfab_api_key` | StringProperty | - | Sketchfab API 密钥 |
| `blendermcp_use_hunyuan3d` | BoolProperty | False | 启用 Hunyuan3D |
| `blendermcp_hunyuan3d_mode` | EnumProperty | LOCAL_API | Hunyuan3D 模式 |
| `blendermcp_hunyuan3d_secret_id` | StringProperty | - | 腾讯云 Secret ID |
| `blendermcp_hunyuan3d_secret_key` | StringProperty | - | 腾讯云 Secret Key |
| `blendermcp_hunyuan3d_api_url` | StringProperty | http://localhost:8081 | 本地 API URL |
| `blendermcp_hunyuan3d_octree_resolution` | IntProperty | 256 | 八叉树分辨率 |
| `blendermcp_hunyuan3d_num_inference_steps` | IntProperty | 20 | 推理步数 |
| `blendermcp_hunyuan3d_guidance_scale` | FloatProperty | 5.5 | 引导比例 |
| `blendermcp_hunyuan3d_texture` | BoolProperty | False | 生成纹理 |

## 6. 辅助方法

### `_get_aabb(obj)` (静态方法)
- 计算世界空间轴对齐包围盒
- 返回 8 个顶点的坐标列表

### `_clean_imported_glb(obj)`
- 移除空父节点
- 重命名 mesh 对象

### `get_tencent_cloud_sign_headers(...)`
- 生成腾讯云 API 签名
- TC3-HMAC-SHA256 算法

## 7. 硬编码凭证

```python
# line 33
RODIN_FREE_TRIAL_KEY = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"
```
