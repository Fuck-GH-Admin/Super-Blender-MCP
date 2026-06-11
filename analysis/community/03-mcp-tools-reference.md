# Blender MCP Community - MCP 工具参考

> 共 16 个 MCP 工具

## 工具总览

| # | 工具名 | 分类 | 读取 | 破坏性 | 说明 |
|---|--------|------|------|--------|------|
| 1 | `blender_get_scene_info` | 场景 | Yes | No | 获取场景信息 |
| 2 | `blender_get_object_info` | 场景 | Yes | No | 获取对象信息 |
| 3 | `blender_create_object` | 对象 | No | No | 创建基本体 |
| 4 | `blender_modify_object` | 对象 | No | No | 修改对象 |
| 5 | `blender_delete_object` | 对象 | No | Yes | 删除对象 |
| 6 | `blender_set_material` | 材质 | No | No | 设置材质 |
| 7 | `blender_render_image` | 渲染 | No | No | 渲染图像 |
| 8 | `blender_execute_code` | 通用 | No | Yes | 执行代码 |
| 9 | `blender_get_polyhaven_categories` | PolyHaven | No | No | 获取分类 |
| 10 | `blender_search_polyhaven_assets` | PolyHaven | No | No | 搜索资产 |
| 11 | `blender_download_polyhaven_asset` | PolyHaven | No | No | 下载资产 |
| 12 | `blender_set_texture` | PolyHaven | No | No | 设置纹理 |
| 13 | `blender_ai_prompt` | Ollama | No | No | AI 提示 |
| 14 | `blender_set_ollama_model` | Ollama | No | No | 设置模型 |
| 15 | `blender_set_ollama_url` | Ollama | No | No | 设置 URL |
| 16 | `blender_get_ollama_models` | Ollama | No | No | 列出模型 |

---

## 1. Pydantic 输入模型

### 1.1 Vec3
```python
class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.z]
```

### 1.2 枚举类型

```python
class ObjectType(str, Enum):
    MESH = "MESH"
    CURVE = "CURVE"
    SURFACE = "SURFACE"
    META = "META"
    FONT = "FONT"
    ARMATURE = "ARMATURE"
    LATTICE = "LATTICE"
    EMPTY = "EMPTY"
    GPENCIL = "GPENCIL"
    CAMERA = "CAMERA"
    LIGHT = "LIGHT"
    SPEAKER = "SPEAKER"
    LIGHT_PROBE = "LIGHT_PROBE"

class PrimitiveType(str, Enum):
    CUBE = "CUBE"
    SPHERE = "SPHERE"
    CYLINDER = "CYLINDER"
    CONE = "CONE"
    TORUS = "TORUS"
    PLANE = "PLANE"
    CIRCLE = "CIRCLE"
    ICO_SPHERE = "ICO_SPHERE"
    GRID = "GRID"
    MONKEY = "MONKEY"

class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"

class PolyHavenAssetType(str, Enum):
    HDRIS = "hdris"
    TEXTURES = "textures"
    MODELS = "models"
    ALL = "all"
```

---

## 2. 场景/对象工具

### 2.1 `blender_get_scene_info`

**位置**: server.py lines 378-403

**参数**: 无

**返回**: 场景摘要，包含:
- scene_name, frame_start, frame_end
- render_engine, resolution_x, resolution_y
- camera 名称
- 所有对象列表 (name, type, location, rotation, scale, visible, material_slots)

**与官方版本差异**: 返回所有对象（无 10 个限制）

### 2.2 `blender_get_object_info`

**位置**: server.py lines 405-438

**输入模型**:
```python
class GetObjectInfoInput(BaseModel):
    object_name: str = Field(..., min_length=1, max_length=256)
    response_format: ResponseFormat = ResponseFormat.JSON
```

**返回**: 对象详细信息
- transforms (rotation 为度数和弧度)
- visibility, parent, children
- MESH: vertex/edge/polygon count
- LIGHT: type, energy, color
- CAMERA: type, focal_length

### 2.3 `blender_create_object`

**位置**: server.py lines 440-482

**输入模型**:
```python
class CreateObjectInput(BaseModel):
    primitive_type: PrimitiveType
    name: str = ""
    location: Vec3 = Vec3()
    rotation: Vec3 = Vec3()
    scale: Vec3 = Vec3(x=1.0, y=1.0, z=1.0)
```

**支持的基本体**: CUBE, SPHERE, CYLINDER, CONE, TORUS, PLANE, CIRCLE, ICO_SPHERE, GRID, MONKEY

### 2.4 `blender_modify_object`

**位置**: server.py lines 484-525

**输入模型**:
```python
class ModifyObjectInput(BaseModel):
    name: str
    location: Vec3 = None
    rotation: Vec3 = None
    scale: Vec3 = None
    visible: bool = None
```

**特性**: 部分更新，仅修改提供的字段

### 2.5 `blender_delete_object`

**位置**: server.py lines 527-560

**输入模型**:
```python
class DeleteObjectInput(BaseModel):
    name: str
```

**注解**: `destructiveHint=True`

---

## 3. 材质/渲染工具

### 3.1 `blender_set_material`

**位置**: server.py lines 562-600

**输入模型**:
```python
class SetMaterialInput(BaseModel):
    object_name: str
    material_name: str
    color: list[float] = None  # RGBA, 0.0-1.0

    @field_validator("color")
    @classmethod
    def validate_color(cls, v):
        if v is None:
            return v
        if len(v) not in (3, 4):
            raise ValueError("Color must have 3 (RGB) or 4 (RGBA) components")
        if len(v) == 3:
            v = v + [1.0]  # 自动添加 alpha
        for c in v:
            if not 0.0 <= c <= 1.0:
                raise ValueError("Color components must be between 0.0 and 1.0")
        return v
```

**实现**: 创建或复用 Principled BSDF 材质，设置 Base Color

### 3.2 `blender_render_image`

**位置**: server.py lines 602-635

**输入模型**:
```python
class RenderImageInput(BaseModel):
    file_path: str  # 绝对路径
```

**实现**: `bpy.ops.render.render(write_still=True)`

---

## 4. 代码执行工具

### 4.1 `blender_execute_code`

**位置**: server.py lines 637-674

**输入模型**:
```python
class ExecuteCodeInput(BaseModel):
    code: str
```

**注解**: `destructiveHint=True`

**实现**: stdout 捕获 + `exec()`

---

## 5. PolyHaven 工具

### 5.1 `blender_get_polyhaven_categories`

**位置**: server.py lines 676-713

**输入模型**:
```python
class GetPolyHavenCategoriesInput(BaseModel):
    asset_type: PolyHavenAssetType = PolyHavenAssetType.HDRIS
```

**特性**: 直接通过 httpx 从 MCP server 调用（不经过 Blender）

### 5.2 `blender_search_polyhaven_assets`

**位置**: server.py lines 715-773

**输入模型**:
```python
class SearchPolyHavenInput(BaseModel):
    asset_type: PolyHavenAssetType = PolyHavenAssetType.ALL
    categories: str = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

**特性**: 分页支持 (limit/offset)

### 5.3 `blender_download_polyhaven_asset`

**位置**: server.py lines 775-830

**输入模型**:
```python
class DownloadPolyHavenInput(BaseModel):
    asset_id: str
    asset_type: PolyHavenAssetType
    resolution: str = "1k"
    file_format: str = None
```

**特性**: 服务器端解析 URL，然后发送到 Blender

### 5.4 `blender_set_texture`

**位置**: server.py lines 832-869

**输入模型**:
```python
class SetTextureInput(BaseModel):
    object_name: str
    texture_id: str
```

---

## 6. Ollama 工具

### 6.1 `blender_ai_prompt`

**位置**: server.py lines 871-907

**输入模型**:
```python
class PromptInput(BaseModel):
    prompt: str
    system_prompt: str = "You are a Blender expert..."
```

**实现**: 发送到 Ollama `/api/generate`

### 6.2 `blender_set_ollama_model`

**位置**: server.py lines 909-935

**输入模型**:
```python
class SetOllamaModelInput(BaseModel):
    model_name: str
```

**实现**: 更新 `_state["ollama_model"]`

### 6.3 `blender_set_ollama_url`

**位置**: server.py lines 937-963

**输入模型**:
```python
class SetOllamaUrlInput(BaseModel):
    url: str
```

**实现**: 更新 `_state["ollama_url"]`

### 6.4 `blender_get_ollama_models`

**位置**: server.py lines 964-998

**参数**: 无

**实现**: GET `http://localhost:11434/api/tags`

---

## 7. MCP 工具注解

所有工具都使用 MCP 注解:

```python
@mcp.tool(
    annotations={
        "readOnlyHint": True/False,
        "destructiveHint": True/False,
        "idempotentHint": True/False,
        "openWorldHint": True/False,
    }
)
```

| 工具 | readOnly | destructive | idempotent | openWorld |
|------|----------|-------------|------------|-----------|
| get_scene_info | Yes | No | Yes | No |
| get_object_info | Yes | No | Yes | No |
| create_object | No | No | No | No |
| modify_object | No | No | No | No |
| delete_object | No | Yes | No | No |
| set_material | No | No | No | No |
| render_image | No | No | No | No |
| execute_code | No | Yes | No | No |
| get_polyhaven_categories | Yes | No | Yes | Yes |
| search_polyhaven_assets | Yes | No | Yes | Yes |
| download_polyhaven_asset | No | No | No | Yes |
| set_texture | No | No | No | No |
| ai_prompt | No | No | No | Yes |
| set_ollama_model | No | No | Yes | No |
| set_ollama_url | No | No | Yes | No |
| get_ollama_models | Yes | No | Yes | Yes |
