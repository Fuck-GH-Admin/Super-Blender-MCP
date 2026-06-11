# Blender MCP 统一开发参考

## 1. 推荐架构

### 1.1 进程拓扑

```
┌─────────────────┐   stdio/http   ┌─────────────────────┐   TCP:9876     ┌─────────────────────┐
│   MCP Client    │ ──────────────>│   FastMCP Server    │ ─────────────>│   Blender Addon     │
│ (Claude Desktop)│<────────────── │   (异步, Pydantic)  │<───────────── │   (bpy.app.timers)  │
└─────────────────┘   JSON-RPC     └─────────────────────┘   JSON+\n     └─────────────────────┘
                                           │                                        │
                                           │ httpx                                   │ bpy API
                                           v                                        v
                                   ┌───────────────┐                       ┌─────────────────┐
                                   │    Ollama     │                       │  Blender 3D     │
                                   └───────────────┘                       └─────────────────┘
```

### 1.2 连接模型

**推荐**: 每命令新连接 + 连接池（可选优化）

**理由**:
- 更简单：无连接状态管理
- 更 resilient：无连接中断问题
- 更易调试
- 连接池可在后期添加以优化性能

### 1.3 通信协议

**推荐**: 换行符终止 JSON

```json
{"type": "<command>", "params": {...}}\n
{"status": "ok", "result": {...}}\n
```

**理由**:
- 明确的消息边界
- 更易解析
- 不依赖 JSON 解析作为分隔符

### 1.4 线程模型

**推荐**: `bpy.app.timers.register` 确保主线程执行

```python
def _handle_client(conn, addr):
    # 读取请求
    request = read_request(conn)

    # 调度到主线程
    result = {}
    def execute():
        result["value"] = handler(request["params"])
        return None  # 返回 None 停止 timer

    bpy.app.timers.register(execute, first_interval=0.0)

    # 等待结果
    while "value" not in result:
        time.sleep(0.01)

    # 发送响应
    send_response(conn, result["value"])
```

**理由**:
- Blender API 不是线程安全的
- 官方版本已验证此方案可行
- 避免崩溃和数据损坏

## 2. 工具清单（合并）

### 2.1 核心工具 (8个)

| # | 工具名 | 来源 | 优先级 | 说明 |
|---|--------|------|--------|------|
| 1 | `get_scene_info` | 两者 | P0 | 场景信息（使用社区版本，返回全部对象） |
| 2 | `get_object_info` | 两者 | P0 | 对象信息（使用社区版本，包含 light/camera） |
| 3 | `create_object` | 社区 | P0 | 创建基本体 |
| 4 | `modify_object` | 社区 | P0 | 修改对象 |
| 5 | `delete_object` | 社区 | P0 | 删除对象 |
| 6 | `set_material` | 社区 | P0 | 设置材质 |
| 7 | `render_image` | 社区 | P0 | 渲染图像 |
| 8 | `execute_code` | 两者 | P0 | 执行代码 |

### 2.2 视口工具 (1个)

| # | 工具名 | 来源 | 优先级 | 说明 |
|---|--------|------|--------|------|
| 9 | `get_viewport_screenshot` | 官方 | P1 | 视口截图 |

### 2.3 PolyHaven 工具 (5个)

| # | 工具名 | 来源 | 优先级 | 说明 |
|---|--------|------|--------|------|
| 10 | `get_polyhaven_categories` | 社区 | P1 | 分类列表（server 端调用） |
| 11 | `search_polyhaven_assets` | 社区 | P1 | 搜索资产（支持分页） |
| 12 | `download_polyhaven_asset` | 官方 | P1 | 下载资产（完整 PBR） |
| 13 | `set_texture` | 官方 | P1 | 应用纹理（完整 PBR 节点图） |
| 14 | `get_polyhaven_status` | 官方 | P2 | 状态检查 |

### 2.4 Sketchfab 工具 (4个)

| # | 工具名 | 来源 | 优先级 | 说明 |
|---|--------|------|--------|------|
| 15 | `get_sketchfab_status` | 官方 | P2 | 状态检查 |
| 16 | `search_sketchfab_models` | 官方 | P2 | 搜索模型 |
| 17 | `get_sketchfab_model_preview` | 官方 | P2 | 获取缩略图 |
| 18 | `download_sketchfab_model` | 官方 | P2 | 下载模型（含 zip-slip 保护） |

### 2.5 Hyper3D 工具 (5个)

| # | 工具名 | 来源 | 优先级 | 说明 |
|---|--------|------|--------|------|
| 19 | `get_hyper3d_status` | 官方 | P2 | 状态检查 |
| 20 | `generate_hyper3d_model_via_text` | 官方 | P2 | 文本生成 3D |
| 21 | `generate_hyper3d_model_via_images` | 官方 | P2 | 图片生成 3D |
| 22 | `poll_rodin_job_status` | 官方 | P2 | 轮询状态 |
| 23 | `import_generated_asset` | 官方 | P2 | 导入资产 |

### 2.6 Hunyuan3D 工具 (4个)

| # | 工具名 | 来源 | 优先级 | 说明 |
|---|--------|------|--------|------|
| 24 | `get_hunyuan3d_status` | 官方 | P2 | 状态检查 |
| 25 | `generate_hunyuan3d_model` | 官方 | P2 | 生成 3D 模型 |
| 26 | `poll_hunyuan_job_status` | 官方 | P2 | 轮询状态 |
| 27 | `import_generated_asset_hunyuan` | 官方 | P2 | 导入资产 |

### 2.7 Ollama 工具 (4个)

| # | 工具名 | 来源 | 优先级 | 说明 |
|---|--------|------|--------|------|
| 28 | `ai_prompt` | 社区 | P2 | AI 提示 |
| 29 | `set_ollama_model` | 社区 | P2 | 设置模型 |
| 30 | `set_ollama_url` | 社区 | P2 | 设置 URL |
| 31 | `get_ollama_models` | 社区 | P2 | 列出模型 |

**总计**: 31 个工具

## 3. 输入验证策略

### 3.1 Pydantic 模型定义

```python
from pydantic import BaseModel, Field, field_validator
from enum import Enum

class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.z]

class PrimitiveType(str, Enum):
    CUBE = "CUBE"
    SPHERE = "SPHERE"
    # ...

class CreateObjectInput(BaseModel):
    primitive_type: PrimitiveType
    name: str = ""
    location: Vec3 = Vec3()
    rotation: Vec3 = Vec3()
    scale: Vec3 = Vec3(x=1.0, y=1.0, z=1.0)

class SetMaterialInput(BaseModel):
    object_name: str
    material_name: str
    color: list[float] = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v):
        if v is None:
            return v
        if len(v) not in (3, 4):
            raise ValueError("Color must have 3 or 4 components")
        if len(v) == 3:
            v = v + [1.0]
        for c in v:
            if not 0.0 <= c <= 1.0:
                raise ValueError("Color components must be 0.0-1.0")
        return v
```

### 3.2 验证位置

- **Server 端**: Pydantic 自动验证
- **Addon 端**: 信任已验证的输入
- **共享模型**: 定义在 `models/` 目录

## 4. 测试策略

### 4.1 测试金字塔

```
        /\
       /  \        E2E 测试 (少量)
      /    \       - 完整流程测试
     /------\
    /        \     集成测试 (适量)
   /          \    - Addon handler 测试
  /------------\   - Client 测试 (mock HTTP)
 /              \  单元测试 (大量)
/                \ - 输入模型验证
                  \- 错误处理
                   \- 工具注解
```

### 4.2 测试覆盖目标

| 组件 | 目标覆盖率 | 测试类型 |
|------|------------|----------|
| 输入模型 | 100% | 单元测试 |
| Server 工具 | 80% | 集成测试 (mock) |
| Addon handler | 80% | 集成测试 (mock bpy) |
| Client 方法 | 90% | 集成测试 (mock HTTP) |
| E2E 流程 | 关键路径 | E2E 测试 |

### 4.3 Mock 策略

**Blender API**:
```python
import sys
from unittest.mock import MagicMock

bpy = MagicMock()
sys.modules["bpy"] = bpy
```

**HTTP 请求**:
```python
@pytest.fixture
def mock_httpx(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr("httpx.AsyncClient", mock)
    return mock
```

**TCP Socket**:
```python
@pytest.fixture
def mock_socket(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("socket.socket", mock)
    return mock
```

## 5. 依赖管理

### 5.1 核心依赖

```toml
dependencies = [
    "mcp[cli]>=1.6.0",
    "fastmcp>=2.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]
```

### 5.2 可选依赖

```toml
[project.optional-dependencies]
client = ["httpx>=0.27.0"]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "black>=24.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
telemetry = ["supabase>=2.0.0"]
```

### 5.3 Blender 插件依赖

- 仅使用 Blender 内置模块
- 不使用 `requests`（使用 `urllib.request`）
- 避免外部依赖

## 6. 安全考虑

### 6.1 Zip-slip 保护

```python
for member in zip_ref.infolist():
    if '..' in member.filename or member.filename.startswith('/'):
        continue
    target_path = os.path.join(extract_dir, member.filename)
    if not os.path.abspath(target_path).startswith(os.path.abspath(extract_dir)):
        continue
```

### 6.2 代码执行沙箱

**当前状态**: 两个版本都没有沙箱

**建议**: 限制可用模块
```python
ALLOWED_MODULES = {"bpy", "mathutils", "math", "random"}

def restricted_import(name, *args, **kwargs):
    if name not in ALLOWED_MODULES:
        raise ImportError(f"Import of {name} is not allowed")
    return original_import(name, *args, **kwargs)

namespace["__builtins__"]["__import__"] = restricted_import
```

### 6.3 API 密钥存储

**推荐**: 环境变量
```python
import os

api_key = os.environ.get("SKETCHFAB_API_KEY", "")
if not api_key:
    return "API key not set. Set SKETCHFAB_API_KEY environment variable."
```

**避免**: 硬编码、Scene Properties（明文存储）

### 6.4 遥测同意

```python
# 检查用户同意
if not user_consent:
    # 剥离敏感数据
    event.pop("prompt", None)
    event.pop("metadata", None)
    event.pop("error_details", None)
```

## 7. MCP 协议合规

### 7.1 工具注解

```python
@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
```

### 7.2 Prompt 模板

```python
@mcp.prompt()
def asset_creation_strategy() -> str:
    """指导 Claude 的资产创建工作流"""
    return """
    优先级顺序:
    1. 检查 Sketchfab 集成
    2. 检查 PolyHaven 集成
    3. 检查 Hyper3D 集成
    4. 检查 Hunyuan3D 集成
    5. 回退到脚本创建
    """
```

### 7.3 传输支持

- **stdio**: Claude Desktop, Cursor
- **streamable_http**: 自定义客户端

## 8. 实施路线图

### Phase 1: 核心 (1-2周)
- 场景/对象 CRUD
- 材质设置
- 渲染
- 代码执行
- 基础测试

### Phase 2: PolyHaven (1周)
- 分类和搜索
- 完整 PBR 纹理导入
- HDRI 导入
- 模型导入

### Phase 3: 视口截图 (3天)
- 捕获 3D 视口
- 尺寸限制
- 返回 Image 对象

### Phase 4: Sketchfab + Hyper3D + Hunyuan3D (2周)
- Sketchfab 搜索、预览、下载
- Hyper3D 文本/图片生成
- Hunyuan3D 集成
- Zip-slip 安全保护

### Phase 5: Ollama 集成 (3天)
- AI prompt
- 模型管理
- 运行时配置

### Phase 6: 客户端 + CLI (1周)
- BlenderMCPClient 类
- 交互式 CLI
- 一次性命令

### Phase 7: 测试 + 文档 (1周)
- 完善测试套件
- API 文档
- 用户指南

**总预计时间**: 6-8周
