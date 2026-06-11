# Blender MCP 双版本对比分析

## 1. 功能矩阵

| 功能 | 官方版本 | 社区版本 |
|------|----------|----------|
| **场景信息** | 限制 10 个对象 | 全部对象 |
| **对象信息** | 基本信息 | 包含 light/camera 数据 |
| **对象 CRUD** | 通过 execute_code | 原生支持 (create/modify/delete) |
| **材质设置** | 通过 execute_code | 原生 set_material |
| **渲染** | 通过 execute_code | 原生 render_image |
| **视口截图** | 支持 | 不支持 |
| **代码执行** | 支持 | 支持 |
| **PolyHaven** | 完整 PBR 节点图 | 简单单贴图 |
| **Sketchfab** | 支持 | 不支持 |
| **Hyper3D** | 支持 | 不支持 |
| **Hunyuan3D** | 支持 | 不支持 |
| **Ollama** | 不支持 | 支持 |
| **遥测** | Supabase | 无 |
| **客户端库** | 无 | BlenderMCPClient |
| **CLI** | 无 | 完整 CLI |
| **测试套件** | 无 | 839 行 |
| **MCP 注解** | 无 | readOnly/destructive/idempotent/openWorld |
| **MCP Prompt** | asset_creation_strategy | 无 |
| **输入验证** | 无 | Pydantic v2 |

## 2. 架构对比

### 2.1 连接模型

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 连接类型 | 持久连接 | 每命令新连接 |
| 连接管理 | 全局单例 | 无状态 |
| 连接验证 | get_polyhaven_status ping | 无 |
| 重连机制 | 自动 | 不需要 |
| 并发安全 | 需要锁 | 天然安全 |

**权衡**:
- 持久连接: 更低延迟，但更复杂
- 每命令连接: 更简单，但有连接开销

### 2.2 通信协议

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 消息分隔 | 无分隔符 | 换行符 `\n` |
| 接收方式 | 累积并尝试 JSON 解析 | 读到连接关闭 |
| 超时时间 | 180秒 | 30秒 |
| 响应状态 | `success` / `error` | `ok` / `error` |
| 缓冲区 | 8192 字节 | 8192 字节 |

**权衡**:
- 无分隔符: 更灵活，但解析更脆弱
- 换行符分隔: 更明确，但需要转义

### 2.3 线程模型

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 主线程调度 | `bpy.app.timers.register` | 直接执行 |
| 线程安全 | 是 | 否 |
| 实现复杂度 | 更高 | 更低 |

**权衡**:
- `bpy.app.timers.register`: 线程安全，但增加复杂度
- 直接执行: 更简单，但可能崩溃

### 2.4 服务器类型

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 工具函数 | 同步 | 异步 |
| 外部调用 | requests (同步) | httpx (异步) |
| 并发性能 | 阻塞 | 非阻塞 |

### 2.5 输入验证

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 验证方式 | 无 | Pydantic v2 |
| 类型检查 | 无 | 有 |
| 范围检查 | 无 | 有 (ge, le, min_length, max_length) |
| 自定义验证 | 无 | 有 (field_validator) |

## 3. 代码质量指标

| 指标 | 官方版本 | 社区版本 |
|------|----------|----------|
| Server 代码行数 | 1186 | 1044 |
| Addon 代码行数 | 2636 | 655 |
| Client 代码行数 | 0 | 497 |
| 测试代码行数 | 0 | 839 |
| **总代码行数** | **3822** | **3035** |
| 依赖数量 | 3 | 4 (+ dev) |
| 构建系统 | setuptools | hatchling |
| 类型注解 | 无 | 有 |
| 文档字符串 | 无 | 有 |
| Linting | 无 | Ruff |
| 类型检查 | 无 | Mypy |

## 4. 集成深度对比

### 4.1 PolyHaven

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| API 调用位置 | Blender addon | MCP server |
| HDRI 节点图 | TexCoord -> Mapping -> Env -> Background -> Output | Env -> Background -> Output |
| 纹理设置 | 完整 PBR (7 通道) | 单贴图 (Diffuse) |
| 颜色空间 | 正确设置 | 未设置 |
| 模型导入 | 多格式支持 | 基本支持 |

### 4.2 纹理通道支持

| 通道 | 官方版本 | 社区版本 |
|------|----------|----------|
| Base Color | 支持 | 支持 |
| Roughness | 支持 | 不支持 |
| Metallic | 支持 | 不支持 |
| Normal | 支持 | 不支持 |
| Displacement | 支持 | 不支持 |
| ARM | 支持 | 不支持 |
| AO | 支持 | 不支持 |

### 4.3 模型导入

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 尺寸归一化 | 支持 | 不支持 |
| Zip-slip 保护 | 支持 | 不支持 |
| 空父节点清理 | 支持 | 不支持 |
| 格式支持 | glTF, FBX, OBJ, blend | 基本 |

## 5. 开发者体验

### 5.1 类型安全

**官方版本**:
```python
@mcp.tool()
def get_object_info(ctx: Context, object_name: str) -> str:
    # 无参数验证
    ...
```

**社区版本**:
```python
class GetObjectInfoInput(BaseModel):
    object_name: str = Field(..., min_length=1, max_length=256)
    response_format: ResponseFormat = ResponseFormat.JSON

@mcp.tool()
async def blender_get_object_info(params: GetObjectInfoInput) -> str:
    # Pydantic 自动验证
    ...
```

### 5.2 测试覆盖

**官方版本**: 无测试

**社区版本**:
```bash
pytest tests/
# 58 tests passed
```

### 5.3 代码组织

**官方版本**:
```
addon.py (2636行) - 所有逻辑混在一起
server.py (1186行) - 所有工具在一个文件
```

**社区版本**:
```
addon.py (655行) - 仅 Blender 相关
server.py (1044行) - 服务器逻辑
client.py (497行) - 客户端库
tests/ (839行) - 测试代码
```

### 5.4 错误处理

**官方版本**:
```python
try:
    response = self.send_command(...)
except Exception as e:
    raise Exception(f"Error: {e}")
```

**社区版本**:
```python
try:
    response = _send_blender_command(...)
except ConnectionRefusedError:
    return "Blender is not running..."
except TimeoutError:
    return "Blender took too long..."
except RuntimeError as e:
    return f"Unexpected error: {e}"
```

## 6. 统一项目建议

### 6.1 从官方版本借鉴

1. **完整 PBR 纹理节点图** (addon.py lines 560-750)
2. **视口截图功能** (addon.py lines 364-419)
3. **Sketchfab 集成** (addon.py lines 1477-1910)
4. **Hyper3D 集成** (addon.py lines 1141-1475)
5. **Hunyuan3D 集成** (addon.py lines 1912-2321)
6. **尺寸归一化** (addon.py)
7. **Zip-slip 安全保护** (addon.py)
8. **Asset Creation Strategy Prompt** (server.py lines 1089-1177)
9. **`bpy.app.timers.register` 线程调度** (addon.py line 170)

### 6.2 从社区版本借鉴

1. **Pydantic v2 输入验证** (server.py lines 168-362)
2. **MCP 工具注解** (server.py)
3. **异步工具函数** (server.py)
4. **每命令连接模型** (server.py lines 68-109)
5. **换行符终止协议** (server.py)
6. **BlenderMCPClient 客户端库** (client.py)
7. **交互式 CLI** (client.py)
8. **测试套件** (tests/)
9. **Ollama 集成** (server.py lines 122-148)
10. **HANDLERS 字典分发** (addon.py lines 432-448)
11. **对象 CRUD 原生工具** (addon.py)
12. **完整的场景信息** (addon.py)

### 6.3 合并策略

**Server 架构**:
```
blender-mcp/
├── server.py           # FastMCP server (异步, Pydantic 验证)
├── tools/
│   ├── scene.py        # 场景/对象工具
│   ├── material.py     # 材质工具
│   ├── polyhaven.py    # PolyHaven 工具
│   ├── sketchfab.py    # Sketchfab 工具
│   ├── hyper3d.py      # Hyper3D 工具
│   ├── hunyuan3d.py    # Hunyuan3D 工具
│   └── ollama.py       # Ollama 工具
├── models/
│   ├── scene.py        # 场景相关 Pydantic 模型
│   ├── material.py     # 材质相关模型
│   └── common.py       # 共享模型 (Vec3, 枚举)
├── client.py           # 客户端库
├── addon.py            # Blender 插件
└── tests/
    ├── test_server.py
    ├── test_client.py
    └── test_addon.py
```

**Addon 架构**:
```
addon.py
├── TCP 服务器 (换行符终止, bpy.app.timers.register)
├── HANDLERS 字典分发
├── 场景/对象 Handler
├── 材质 Handler (完整 PBR)
├── PolyHaven Handler
├── Sketchfab Handler
├── Hyper3D Handler
├── Hunyuan3D Handler
└── UI 面板 (集成开关, API 密钥)
```

**协议选择**:
- 换行符终止 JSON (更易解析)
- 每命令新连接 (更简单)
- 30秒超时 (更合理)

**验证策略**:
- Pydantic v2 在 server 端验证
- Addon 端信任已验证的输入
- 共享模型定义

**测试策略**:
- 输入模型单元测试
- Handler 测试 (mock bpy)
- 客户端测试 (mock HTTP)
- 集成测试 (可选)
