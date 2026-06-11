# Blender Super MCP

通过自然语言从 opencode 或 Claude Code 控制 Blender 3D。融合了官方版 (ahujasid) 和社区版 (blender-open-mcp) 的优点。

## 架构

```
opencode/Claude Code ──stdio──> MCP Server ──TCP:9876──> Blender Addon
                                    │                         │
                                    │ httpx                   │ bpy API
                                    v                         v
                                 Ollama                   Blender 3D
```

- **MCP 服务器** (`superMCP/mcp_server.py`): FastMCP 服务器，通过 stdio 通信
- **Blender 插件** (`superMCP/addon.py`): Blender 内部的 TCP 服务器，在主线程执行 bpy 命令
- **Ollama** (可选): 本地运行的 LLM，用于 AI 提示

## 快速开始

### 1. 在 Blender 中安装插件

1. 打开 Blender → 编辑 → 偏好设置 → 插件
2. 下拉菜单 → "从磁盘安装" → 选择 `superMCP/addon.py`
3. 勾选启用 "Blender Super MCP"
4. TCP 服务器会在插件启用时自动启动。在 3D 视口按 N → Super MCP 面板查看状态

### 2. 配置 opencode / Claude Code

**opencode** (通过项目配置自动加载):
仓库中的 `opencode.json` 已定义 MCP 服务器 — 直接打开项目即可。

**Claude Code:**
```bash
claude mcp add --transport stdio blender -- python /绝对路径/superMCP/mcp_server.py
```

### 3. 开始使用

让你的 AI 助手控制 Blender：
- "在位置 (1, 0, 0) 创建一个红色立方体"
- "设置一个 PolyHaven 的 HDRI 环境"
- "在 Sketchfab 搜索汽车模型"

## 可用工具 (31 个)

### 核心 (8 个)
| 工具 | 说明 |
|------|------|
| `blender_get_scene_info` | 获取完整的场景摘要 |
| `blender_get_object_info` | 获取物体详细信息（网格统计、修改器、材质）|
| `blender_create_object` | 创建基础几何体（立方体、球体、圆柱、环面、猴头等）|
| `blender_modify_object` | 移动、旋转、缩放、切换可见性 |
| `blender_delete_object` | 删除物体 |
| `blender_set_material` | 创建/设置基于 Principled BSDF 的材质颜色 |
| `blender_render_image` | 渲染场景到文件 |
| `blender_execute_code` | 执行任意 Python 代码（复杂材质、修改器、几何节点等）|

### 视口 (1 个)
| 工具 | 说明 |
|------|------|
| `blender_get_viewport_screenshot` | 截取 3D 视口截图 |

### PolyHaven (5 个)
| 工具 | 说明 |
|------|------|
| `blender_get_polyhaven_categories` | 浏览分类（HDRI/纹理/模型）|
| `blender_search_polyhaven_assets` | 按类型和分类搜索资源 |
| `blender_download_polyhaven_asset` | 下载 HDRI 或纹理到 Blender |
| `blender_set_texture` | 应用完整的 PBR 纹理节点图 |
| `blender_download_polyhaven_model` | 下载并导入 3D 模型 (gltf/glb/fbx/obj/blend) |

### Sketchfab (需 API 密钥) (4 个)
| 工具 | 说明 |
|------|------|
| `blender_get_sketchfab_status` | 检查集成状态和 API 密钥有效性 |
| `blender_search_sketchfab_models` | 搜索 3D 模型 |
| `blender_get_sketchfab_model_preview` | 获取模型缩略图 (base64) |
| `blender_download_sketchfab_model` | 下载并导入模型 |

### Hyper3D Rodin (AI 3D 生成) (5 个)
| 工具 | 说明 |
|------|------|
| `blender_get_hyper3d_status` | 检查 Hyper3D 配置 |
| `blender_generate_hyper3d_model_via_text` | 文本生成 3D 模型 |
| `blender_generate_hyper3d_model_via_images` | 图片生成 3D 模型 |
| `blender_poll_rodin_job_status` | 查询生成任务进度 |
| `blender_import_generated_asset` | 导入完成的生成结果到场景 |

### Hunyuan3D (腾讯 AI 3D 生成) (4 个)
| 工具 | 说明 |
|------|------|
| `blender_get_hunyuan3d_status` | 检查 Hunyuan3D 配置 |
| `blender_generate_hunyuan3d_model` | 从文本或图片生成 3D 模型 |
| `blender_poll_hunyuan_job_status` | 查询生成任务进度 |
| `blender_import_generated_asset_hunyuan` | 导入完成的生成结果 (zip 含 OBJ) |

### Ollama (本地 LLM) (4 个)
| 工具 | 说明 |
|------|------|
| `blender_ai_prompt` | 向本地 Ollama 发送自然语言提示 |
| `blender_set_ollama_model` | 切换 Ollama 模型 |
| `blender_set_ollama_url` | 设置 Ollama 服务器地址 |
| `blender_get_ollama_models` | 列出可用模型 |

## 关键修复与改进

- **线程安全**: 所有命令通过定时器队列在 Blender 主线程执行 — 消除了 TCP 线程的 Context 错误
- **自动启动**: TCP 服务器在插件注册时自动启动，无需手动点击"启动服务器"
- **健壮的 TCP 接收**: 修复了单次 `recv()` 截断问题 — 改用带 JSON 校验的缓冲循环；已通过 628KB 负载测试
- **外部集成修复**: 修复了 26 处 `blendermcp_*` → `supermcp_*` 属性名不匹配问题 — Sketchfab、Hyper3D、Hunyuan3D 现在正常工作

## CLI 选项

```
python superMCP/mcp_server.py [选项]

  --transport {stdio,streamable_http}  MCP 传输方式 (默认: stdio)
  --host HOST                          HTTP 服务主机
  --port PORT                          HTTP 服务端口
  --blender-host HOST                  Blender TCP 主机 (默认: localhost)
  --blender-port PORT                  Blender TCP 端口 (默认: 9876)
  --ollama-url URL                     Ollama 服务器地址
  --ollama-model MODEL                 默认 Ollama 模型
```

## 许可证

MIT
