# Blender Super MCP - 使用指南

## 这是什么

Blender Super MCP 让你可以通过自然语言从 Claude Code 控制 Blender。让 AI 帮你创建物体、修改材质、搭建场景、渲染输出——全程无需触碰 Blender 界面。

## 快速设置

### 1. 安装 Python 依赖

```bash
pip install "mcp[cli]>=1.6.0" "fastmcp>=2.0.0" "httpx>=0.27.0" "pydantic>=2.0.0"
```

### 2. 安装 Blender 插件

1. 打开 Blender → 编辑 → 偏好设置 → 插件
2. 点击 **安装** → 选择 `superMCP/addon.py`
3. 勾选启用 **"Blender Super MCP"**

### 3. 确认服务器已启动

插件启用后，TCP 服务器会自动启动。在 3D 视口按 **N** 打开侧栏 → **Super MCP** 标签页，确认显示 "Server Running"。

### 4. 向 Claude Code 注册 MCP 服务器

```bash
claude mcp add --transport stdio blender -- python /绝对路径/superMCP/mcp_server.py
```

服务器会自动扫描 Blender 端口（9876-9890），无需手动指定端口。

如果需要指定端口：

```bash
claude mcp add --transport stdio blender -- python /路径/mcp_server.py --blender-port 9880
```

### 5. 开始使用

在项目目录下打开 Claude Code，尝试：

- "获取当前 Blender 场景信息"
- "在 (2, 0, 0) 位置创建一个红色球体"
- "让立方体使用玻璃材质"
- "渲染场景"

## CLI 选项

```
python mcp_server.py [选项]

  --transport {stdio,streamable_http}  MCP 传输方式 (默认: stdio)
  --host HOST                          HTTP 服务主机 (默认: 0.0.0.0)
  --port PORT                          HTTP 服务端口 (默认: 8000)
  --blender-host HOST                  Blender TCP 主机 (默认: 127.0.0.1)
  --blender-port PORT                  Blender TCP 端口 (0 = 自动发现, 默认: 0)
  --ollama-url URL                     Ollama 服务器地址
  --ollama-model MODEL                 默认 Ollama 模型
```

环境变量: `BLENDER_HOST`, `BLENDER_PORT`

## 可用工具 (31 个)

### 场景查询
| 工具 | 说明 |
|------|------|
| `blender_get_scene_info` | 完整场景信息：所有物体、相机、帧范围、渲染设置 |
| `blender_get_object_info` | 详细物体信息：变换、网格统计、材质、修改器 |
| `blender_get_viewport_screenshot` | 截取 3D 视口截图 |

### 物体操作
| 工具 | 说明 |
|------|------|
| `blender_create_object` | 创建基础几何体：立方体、球体、圆柱、圆锥、环面、平面、猴头等 |
| `blender_modify_object` | 修改位置、旋转、缩放、可见性 |
| `blender_delete_object` | 删除物体 |
| `blender_set_material` | 创建/分配 Principled BSDF 材质 (RGBA 颜色) |
| `blender_render_image` | 渲染场景到文件 |
| `blender_execute_code` | 执行任意 bpy Python 代码（万能工具）|

### PolyHaven (免费 PBR 资源)
| 工具 | 说明 |
|------|------|
| `blender_get_polyhaven_categories` | 列出资源分类 |
| `blender_search_polyhaven_assets` | 搜索纹理、HDRI、模型 |
| `blender_download_polyhaven_asset` | 下载 HDRI/纹理 |
| `blender_set_texture` | 应用完整 PBR 纹理节点图 |
| `blender_download_polyhaven_model` | 下载 3D 模型 (glTF, FBX, OBJ, blend) |

### Sketchfab
| 工具 | 说明 |
|------|------|
| `blender_get_sketchfab_status` | 检查 API 密钥状态 |
| `blender_search_sketchfab_models` | 搜索模型 |
| `blender_get_sketchfab_model_preview` | 获取缩略图 |
| `blender_download_sketchfab_model` | 下载并导入模型 |

### Hyper3D Rodin (AI 3D 生成)
| 工具 | 说明 |
|------|------|
| `blender_get_hyper3d_status` | 检查集成状态 |
| `blender_generate_hyper3d_model_via_text` | 文本生成 3D |
| `blender_generate_hyper3d_model_via_images` | 图片生成 3D |
| `blender_poll_rodin_job_status` | 查询生成任务 |
| `blender_import_generated_asset` | 导入结果 |

### Hunyuan3D (腾讯 AI 3D)
| 工具 | 说明 |
|------|------|
| `blender_get_hunyuan3d_status` | 检查集成状态 |
| `blender_generate_hunyuan3d_model` | 生成 3D 模型 |
| `blender_poll_hunyuan_job_status` | 查询生成任务 |
| `blender_import_generated_asset_hunyuan` | 导入结果 |

### Ollama (本地 LLM)
| 工具 | 说明 |
|------|------|
| `blender_ai_prompt` | 向本地 Ollama 发送提示 |
| `blender_set_ollama_model` | 切换模型 |
| `blender_set_ollama_url` | 设置服务器地址 |
| `blender_get_ollama_models` | 列出可用模型 |

## 提示

- **视口模式很重要**：在 Blender 中使用材质预览或渲染模式才能看到材质变化
- **Cycles vs EEVEE**：复杂材质（玻璃、体积、透射）在 Cycles 下效果最佳
- **性能优化**：如果 Blender 变卡，可降低视口采样、添加精简修改器、隐藏重型粒子系统
- **执行代码**：内置工具无法完成的操作，用 `blender_execute_code` 运行任意 Python 代码

## 架构

```
Claude Code  --stdio-->  MCP 服务器 (mcp_server.py)  --TCP-->  Blender 插件 (addon.py)
                              |                                       |
                              | httpx                                 | bpy API
                              v                                       v
                           Ollama                                 Blender 3D
```

MCP 服务器和 Blender 插件之间通过以换行符分隔的 JSON 在 TCP 上通信。服务器在首次命令时自动发现 Blender 端口（扫描 9876-9890）。
