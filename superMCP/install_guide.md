# Blender Super MCP - 安装指南

## 前置要求

- **Blender** 3.0 或更新版本
- **Python** 3.10 或更新版本
- **opencode** 或 **Claude Code** CLI
- **Ollama**（可选，用于 AI 提示）

## 第一步：安装 Python 依赖

```bash
pip install "mcp[cli]>=1.6.0" "fastmcp>=2.0.0" "httpx>=0.27.0" "pydantic>=2.0.0"
```

## 第二步：安装 Blender 插件

1. 打开 Blender
2. 进入 **编辑 → 偏好设置 → 插件**
3. 点击右上角 **安装...**
4. 选择 `superMCP/addon.py`
5. 勾选 **"界面: Blender Super MCP"** 启用插件

## 第三步：验证插件服务器

插件启用后会自动启动 TCP 服务器。验证方法：

1. 在 3D 视口中按 **N** 打开侧栏
2. 找到 **"Super MCP"** 标签页
3. 应该看到 "Server Running" 及端口 9876

### 配置外部集成（可选）

在 Super MCP 面板中，可以启用：
- **Poly Haven**：免费 CC0 纹理、HDRI 和模型
- **Hyper3D Rodin**：AI 3D 生成（需要 API 密钥）
- **Sketchfab**：3D 模型库（需要 API 密钥）
- **Hunyuan 3D**：腾讯 3D 生成（需要 API 密钥或本地服务器）

## 第四步：配置 AI 客户端

### 选项 A：使用 opencode（推荐）

本项目已包含 `opencode.json`，直接在 opencode 中打开项目目录即可自动配置。

### 选项 B：使用 Claude Code

```bash
claude mcp add --transport stdio blender -- python /绝对路径/superMCP/mcp_server.py
```

### 选项 C：HTTP 模式（非 CLI 客户端）

```bash
python superMCP/mcp_server.py --transport streamable_http --port 8000
```

## 第五步：测试

在 AI 客户端中尝试输入：
```
获取当前 Blender 场景信息
```

如果成功，你会看到 Blender 场景中的对象列表。

## 故障排除

### "Cannot connect to Blender add-on"
- 确保 Blender 已打开且插件已启用
- 在 Super MCP 面板（N 侧栏）确认显示 "Server Running"
- 如果服务器停止，尝试在偏好设置中禁用后重新启用插件
- 检查端口 9876 是否被占用

### "Invalid JSON response"
- 插件可能已崩溃，检查 Blender 控制台错误信息
- 重启插件服务器

### 外部集成不工作
- PolyHaven：无需 API 密钥，在面板中启用即可
- Sketchfab：从 sketchfab.com → Settings → API Keys 获取密钥
- Hyper3D：使用面板中的免费试用密钥或自行获取
- Hunyuan3D：需要腾讯云凭证或本地 Hunyuan3D 服务器

### Ollama 无响应
```bash
# 确保 Ollama 正在运行
ollama serve

# 拉取模型
ollama pull llama3.2
```

## 可选：Ollama 设置

Ollama 提供本地 AI 能力（无需云端 API）：

```bash
# 安装 Ollama（macOS/Linux）
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull llama3.2

# 启动服务器
ollama serve
```

MCP 服务器默认连接 `http://localhost:11434` 的 Ollama，可通过 `--ollama-url` 修改。
