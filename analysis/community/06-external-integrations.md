# Blender MCP Community - 外部集成

## 1. PolyHaven

### 1.1 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `https://api.polyhaven.com/categories/{asset_type}` | GET | 获取分类 |
| `https://api.polyhaven.com/assets` | GET | 搜索资产 |
| `https://api.polyhaven.com/files/{asset_id}` | GET | 获取下载链接 |

### 1.2 架构特点

**与官方版本的关键差异**: 分类和搜索直接从 MCP Server 调用（不经过 Blender）

```
MCP Server ──httpx──> PolyHaven API
     │
     └──> Blender Addon (仅下载和导入)
```

**优势**: 减少 Blender 负载，响应更快

### 1.3 分类获取

**实现位置**: server.py lines 676-713

```python
async with httpx.AsyncClient() as client:
    resp = await client.get(f"{POLYHAVEN_API_BASE}/categories/{asset_type}")
    return resp.json()
```

### 1.4 资产搜索

**实现位置**: server.py lines 715-773

**特性**:
- 分页支持 (limit/offset)
- 直接从 server 端调用
- 返回资产 ID 和元数据

### 1.5 资产下载

**实现位置**: server.py lines 775-830

**流程**:
1. Server 端解析下载 URL
2. 发送 URL 到 Blender addon
3. Addon 下载并导入

### 1.6 HDRI 设置

**实现位置**: addon.py line 319

**节点图** (比官方版本简单):
```
Environment Texture -> Background -> Output World
```

**注意**: 没有 TexCoord 和 Mapping 节点（官方版本有）

### 1.7 纹理设置

**实现位置**: addon.py line 374

**节点图** (简单版本):
```
Image Texture -> Principled BSDF -> Material Output
```

**注意**: 仅设置单个漫反射贴图（官方版本有完整的 PBR 节点图）

---

## 2. Ollama

### 2.1 概述

Ollama 是一个本地运行大型语言模型的工具。社区版本直接集成了 Ollama API。

### 2.2 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `http://localhost:11434/api/generate` | POST | 生成文本 |
| `http://localhost:11434/api/tags` | GET | 列出可用模型 |

### 2.3 文本生成

**实现位置**: server.py lines 122-148

```python
async def _query_ollama(prompt: str, system_prompt: str = None) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_state['ollama_url']}/api/generate",
            json={
                "model": _state["ollama_model"],
                "prompt": prompt,
                "system": system_prompt or "You are a Blender expert...",
                "stream": False,
            },
            timeout=60.0,
        )
        return resp.json()["response"]
```

### 2.4 默认系统提示

```
You are a Blender 3D modeling expert. Help the user with their Blender questions
and provide clear, actionable advice. When suggesting Python code, use the bpy module.
```

### 2.5 模型管理

**设置模型** (server.py lines 909-935):
```python
@mcp.tool()
async def blender_set_ollama_model(params: SetOllamaModelInput) -> str:
    _state["ollama_model"] = params.model_name
    return f"Ollama model set to: {params.model_name}"
```

**设置 URL** (server.py lines 937-963):
```python
@mcp.tool()
async def blender_set_ollama_url(params: SetOllamaUrlInput) -> str:
    _state["ollama_url"] = params.url
    return f"Ollama URL set to: {params.url}"
```

**列出模型** (server.py lines 964-998):
```python
@mcp.tool()
async def blender_get_ollama_models() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{_state['ollama_url']}/api/tags")
        models = resp.json().get("models", [])
        return "\n".join(m["name"] for m in models)
```

### 2.6 运行时配置

Ollama URL 和模型可以在运行时通过工具调用更改:

```python
# 修改状态
_state = {"ollama_url": DEFAULT_OLLAMA_URL, "ollama_model": DEFAULT_OLLAMA_MODEL}
```

### 2.7 使用场景

1. **自然语言交互**: 用户通过 `blender_ai_prompt` 与 Ollama 对话
2. **Blender 专家**: 系统提示定位为 Blender 专家
3. **代码生成**: Ollama 可以生成 bpy 代码
4. **本地运行**: 无需外部 API 密钥

---

## 3. 与官方版本的集成差异

| 集成 | 官方版本 | 社区版本 |
|------|----------|----------|
| PolyHaven | 完整 PBR 节点图 | 简单单贴图 |
| PolyHaven API | 通过 Blender addon 调用 | 直接从 server 调用 |
| Sketchfab | 支持 | 不支持 |
| Hyper3D | 支持 | 不支持 |
| Hunyuan3D | 支持 | 不支持 |
| Ollama | 不支持 | 支持 |
| 遥测 | Supabase | 无 |

---

## 4. 缺失的集成

社区版本不包含以下官方版本的集成:

### 4.1 Sketchfab
- 3D 模型搜索和下载
- Token 认证
- Zip-slip 安全保护
- 尺寸归一化

### 4.2 Hyper3D Rodin
- 文本/图片生成 3D 模型
- 双模式 (MAIN_SITE/FAL_AI)
- 轮询状态
- GLB 导入

### 4.3 Hunyuan3D
- 腾讯云 API
- 本地 API
- OBJ 导入

### 4.4 视口截图
- 捕获 3D 视口
- 返回 Image 对象

---

## 5. 扩展建议

如果要在社区版本基础上添加更多集成:

1. **Sketchfab**: 参考官方版本的 `download_sketchfab_model` 实现
2. **Hyper3D**: 参考官方版本的 `generate_hyper3d_model_via_text` 实现
3. **Hunyuan3D**: 参考官方版本的 `generate_hunyuan3d_model` 实现
4. **视口截图**: 参考官方版本的 `get_viewport_screenshot` 实现
5. **PBR 纹理**: 参考官方版本的 `set_texture` 实现（完整节点图）
