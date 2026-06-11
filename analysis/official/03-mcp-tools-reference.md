# Blender MCP Official - MCP 工具参考

> 共 22 个 MCP 工具 + 1 个 MCP Prompt

## 工具总览

| # | 工具名 | 分类 | 参数 | 说明 |
|---|--------|------|------|------|
| 1 | `get_scene_info` | 场景 | ctx | 获取场景信息 |
| 2 | `get_object_info` | 场景 | ctx, object_name | 获取对象详细信息 |
| 3 | `get_viewport_screenshot` | 场景 | ctx, max_size=800 | 截取视口截图 |
| 4 | `execute_blender_code` | 通用 | ctx, code | 执行任意 Python 代码 |
| 5 | `get_polyhaven_categories` | PolyHaven | ctx, asset_type="hdris" | 获取分类列表 |
| 6 | `search_polyhaven_assets` | PolyHaven | ctx, asset_type="all", categories=None | 搜索资产 |
| 7 | `download_polyhaven_asset` | PolyHaven | ctx, asset_id, asset_type, resolution="1k", file_format=None | 下载并导入资产 |
| 8 | `set_texture` | PolyHaven | ctx, object_name, texture_id | 应用纹理 |
| 9 | `get_polyhaven_status` | PolyHaven | ctx | 检查 PolyHaven 是否启用 |
| 10 | `get_hyper3d_status` | Hyper3D | ctx | 检查 Hyper3D 是否启用 |
| 11 | `generate_hyper3d_model_via_text` | Hyper3D | ctx, text_prompt, bbox_condition=None | 文本生成 3D 模型 |
| 12 | `generate_hyper3d_model_via_images` | Hyper3D | ctx, input_image_paths=None, input_image_urls=None, bbox_condition=None | 图片生成 3D 模型 |
| 13 | `poll_rodin_job_status` | Hyper3D | ctx, subscription_key=None, request_id=None | 轮询生成状态 |
| 14 | `import_generated_asset` | Hyper3D | ctx, name, task_uuid=None, request_id=None | 导入生成的资产 |
| 15 | `get_sketchfab_status` | Sketchfab | ctx | 检查 Sketchfab 是否启用 |
| 16 | `search_sketchfab_models` | Sketchfab | ctx, query, categories=None, count=20, downloadable=True | 搜索模型 |
| 17 | `get_sketchfab_model_preview` | Sketchfab | ctx, uid | 获取模型缩略图 |
| 18 | `download_sketchfab_model` | Sketchfab | ctx, uid, target_size | 下载并导入模型 |
| 19 | `get_hunyuan3d_status` | Hunyuan3D | ctx | 检查 Hunyuan3D 是否启用 |
| 20 | `generate_hunyuan3d_model` | Hunyuan3D | ctx, text_prompt=None, input_image_url=None | 生成 3D 模型 |
| 21 | `poll_hunyuan_job_status` | Hunyuan3D | ctx, job_id=None | 轮询生成状态 |
| 22 | `import_generated_asset_hunyuan` | Hunyuan3D | ctx, name, zip_file_url | 导入生成的资产 |

---

## 1. 场景/对象检查工具

### 1.1 `get_scene_info`

**位置**: server.py lines 254-266

**参数**: `ctx: Context`

**返回**: JSON 字符串，包含:
- `scene_name`: 场景名称
- `object_count`: 对象总数
- `objects`: 前 10 个对象的列表（name, type, location）
- `material_count`: 材质数量

**注意**: 静默限制为前 10 个对象

**Addon 实现** (addon.py lines 271-303):
```python
def get_scene_info(self):
    scene = bpy.context.scene
    objects = []
    for obj in scene.objects[:10]:  # 限制10个
        objects.append({
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location)
        })
    return {
        "scene_name": scene.name,
        "object_count": len(scene.objects),
        "objects": objects,
        "material_count": len(bpy.data.materials)
    }
```

### 1.2 `get_object_info`

**位置**: server.py lines 268-285

**参数**: `ctx: Context`, `object_name: str`

**返回**: JSON 字符串，包含:
- `name`: 对象名称
- `type`: 对象类型
- `location`: 位置 [x, y, z]
- `rotation`: 旋转 [x, y, z]（弧度）
- `scale`: 缩放 [x, y, z]
- `visible`: 是否可见
- `materials`: 材质列表
- `mesh_stats`: 网格统计（仅 MESH 类型）: vertex_count, edge_count, polygon_count
- `world_bounding_box`: 世界空间包围盒（仅 MESH 类型，8个顶点）

**Addon 实现** (addon.py lines 327-362)

### 1.3 `get_viewport_screenshot`

**位置**: server.py lines 287-328

**参数**: `ctx: Context`, `max_size: int = 800`

**返回**: `Image` 对象（PNG 格式）

**实现细节**:
- 查找 3D 视口区域 (`VIEW_3D`)
- 使用 `bpy.ops.screen.screenshot_area()` 配合 `temp_override`
- 如果图像超过 `max_size`，等比缩放
- 保存为临时文件后读取

**Addon 实现** (addon.py lines 364-419)

### 1.4 `execute_blender_code`

**位置**: server.py lines 331-347

**参数**: `ctx: Context`, `code: str`

**返回**: 代码执行的 stdout 输出

**Addon 实现** (addon.py lines 421-436):
```python
def execute_code(self, params):
    code = params.get("code", "")
    namespace = {"bpy": bpy}
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        exec(code, namespace)
        output = buffer.getvalue()
        return {"result": output}
    except Exception as e:
        return {"error": str(e)}
    finally:
        sys.stdout = old_stdout
```

---

## 2. PolyHaven 集成工具

### 2.1 `get_polyhaven_categories`

**位置**: server.py lines 349-380

**参数**: `ctx: Context`, `asset_type: str = "hdris"` (可选: "hdris", "textures", "models", "all")

**返回**: JSON 字符串，包含分类列表

**Addon 实现**: 调用 `https://api.polyhaven.com/categories/{asset_type}`

### 2.2 `search_polyhaven_assets`

**位置**: server.py lines 382-430

**参数**: `ctx: Context`, `asset_type: str = "all"`, `categories: str = None`

**返回**: JSON 字符串，包含最多 20 个资产（按下载量排序）

**Addon 实现**: 调用 `https://api.polyhaven.com/assets`

### 2.3 `download_polyhaven_asset`

**位置**: server.py lines 432-482

**参数**: `ctx: Context`, `asset_id: str`, `asset_type: str`, `resolution: str = "1k"`, `file_format: str = None`

**返回**: 导入结果描述

**实现细节**:
- **HDRI**: 创建世界节点树 (TexCoord -> Mapping -> Environment Texture -> Background -> Output World)
- **纹理**: 下载所有可用贴图，创建 Principled BSDF 材质，设置正确的颜色空间
- **模型**: 支持 glTF, FBX, OBJ, blend 格式

### 2.4 `set_texture`

**位置**: server.py lines 484-542

**参数**: `ctx: Context`, `object_name: str`, `texture_id: str`

**返回**: 应用结果描述

**实现细节**: 完整 PBR 节点设置:
- Base Color
- Roughness
- Metallic
- Normal
- Displacement
- ARM (Ambient Occlusion + Roughness + Metallic)
- AO (Ambient Occlusion)

### 2.5 `get_polyhaven_status`

**位置**: server.py lines 544-561

**参数**: `ctx: Context`

**返回**: PolyHaven 启用状态

---

## 3. Hyper3D Rodin 集成工具

### 3.1 `get_hyper3d_status`

**位置**: server.py lines 563-582

**参数**: `ctx: Context`

**返回**: Hyper3D 启用状态和模式

### 3.2 `generate_hyper3d_model_via_text`

**位置**: server.py lines 805-840

**参数**: `ctx: Context`, `text_prompt: str`, `bbox_condition: list[float] = None`

**返回**: `task_uuid` 和 `subscription_key`

**实现细节**:
- MAIN_SITE 模式: POST 到 `https://hyperhuman.deemos.com/api/v2/rodin`
- FAL_AI 模式: POST 到 `https://queue.fal.run/fal-ai/hyper3d/rodin`
- `bbox_condition` 归一化为整数，最大比例 100

### 3.3 `generate_hyper3d_model_via_images`

**位置**: server.py lines 842-897

**参数**: `ctx: Context`, `input_image_paths: list[str] = None`, `input_image_urls: list[str] = None`, `bbox_condition: list[float] = None`

**返回**: `task_uuid` 和 `subscription_key`

### 3.4 `poll_rodin_job_status`

**位置**: server.py lines 899-941

**参数**: `ctx: Context`, `subscription_key: str = None`, `request_id: str = None`

**返回**: 生成状态

### 3.5 `import_generated_asset`

**位置**: server.py lines 943-975

**参数**: `ctx: Context`, `name: str`, `task_uuid: str = None`, `request_id: str = None`

**返回**: 导入结果

**实现细节**:
- 下载 GLB 文件
- 使用 `bpy.ops.import_scene.gltf` 导入
- 清理空父节点
- 重命名 mesh

---

## 4. Sketchfab 集成工具

### 4.1 `get_sketchfab_status`

**位置**: server.py lines 584-601

**参数**: `ctx: Context`

**返回**: Sketchfab 启用状态

### 4.2 `search_sketchfab_models`

**位置**: server.py lines 603-678

**参数**: `ctx: Context`, `query: str`, `categories: str = None`, `count: int = 20`, `downloadable: bool = True`

**返回**: 模型列表（uid, name, author, face_count, like_count, view_count, thumbnails）

### 4.3 `get_sketchfab_model_preview`

**位置**: server.py lines 680-720

**参数**: `ctx: Context`, `uid: str`

**返回**: `Image` 对象（缩略图）

### 4.4 `download_sketchfab_model`

**位置**: server.py lines 722-794

**参数**: `ctx: Context`, `uid: str`, `target_size: float`

**返回**: 导入结果

**实现细节**:
- 使用 Token 认证 (`Authorization: Token {api_key}`)
- 下载 ZIP 文件
- **Zip-slip 安全检查**: 防止路径遍历攻击
- 使用 `bpy.ops.import_scene.gltf` 导入
- **尺寸归一化**: 缩放到 `target_size`

---

## 5. Hunyuan3D 集成工具

### 5.1 `get_hunyuan3d_status`

**位置**: server.py lines 977-992

**参数**: `ctx: Context`

**返回**: Hunyuan3D 启用状态和模式

### 5.2 `generate_hunyuan3d_model`

**位置**: server.py lines 994-1029

**参数**: `ctx: Context`, `text_prompt: str = None`, `input_image_url: str = None`

**返回**: `job_id`

**实现细节**:
- OFFICIAL_API: 腾讯云 Hunyuan API，TC3-HMAC-SHA256 签名
- LOCAL_API: 本地服务器端点
- 文本提示限制 200 字符

### 5.3 `poll_hunyuan_job_status`

**位置**: server.py lines 1031-1058

**参数**: `ctx: Context`, `job_id: str = None`

**返回**: 生成状态

### 5.4 `import_generated_asset_hunyuan`

**位置**: server.py lines 1060-1086

**参数**: `ctx: Context`, `name: str`, `zip_file_url: str`

**返回**: 导入结果

**实现细节**:
- 下载 ZIP，提取 OBJ
- Blender 4.0+: 使用 `bpy.ops.wm.obj_import`
- Blender <4.0: 使用 `bpy.ops.import_scene.obj`

---

## 6. MCP Prompt

### `asset_creation_strategy`

**位置**: server.py lines 1089-1177

**用途**: 指导 Claude 的资产创建工作流

**优先级顺序**:
1. 检查 Sketchfab 集成
2. 检查 PolyHaven 集成
3. 检查 Hyper3D 集成
4. 检查 Hunyuan3D 集成
5. 回退到脚本创建
