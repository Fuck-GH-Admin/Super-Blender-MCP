# Blender MCP Community - 依赖与构建

## 1. 项目配置

**文件**: `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "blender-open-mcp"
version = "2.0.0"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "Nirajan Dhakal"}]
dependencies = [
    "mcp[cli]>=1.6.0",
    "fastmcp>=2.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
client = ["httpx>=0.27.0"]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "black>=24.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

## 2. Python 依赖

### 2.1 运行时依赖

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| `mcp[cli]` | >=1.6.0 | MCP 协议框架 |
| `fastmcp` | >=2.0.0 | FastMCP 服务器框架 |
| `httpx` | >=0.27.0 | 异步 HTTP 客户端 |
| `pydantic` | >=2.0.0 | 数据验证 |

### 2.2 可选依赖

**client**:
| 包名 | 版本要求 | 用途 |
|------|----------|------|
| `httpx` | >=0.27.0 | HTTP 客户端 |

**dev**:
| 包名 | 版本要求 | 用途 |
|------|----------|------|
| `pytest` | >=8.0.0 | 测试框架 |
| `pytest-asyncio` | >=0.23.0 | 异步测试支持 |
| `black` | >=24.0.0 | 代码格式化 |
| `ruff` | >=0.4.0 | Linting |
| `mypy` | >=1.10.0 | 类型检查 |

## 3. Blender 插件依赖

### 3.1 内置模块

| 模块 | 用途 |
|------|------|
| `bpy` | Blender Python API |
| `mathutils` | 数学工具 |
| `socket` | TCP 通信 |
| `threading` | 多线程 |
| `json` | JSON 处理 |
| `io` | StringIO |
| `sys` | stdout 重定向 |
| `os` | 文件操作 |
| `urllib.request` | HTTP 请求 (PolyHaven API) |
| `traceback` | 异常追踪 |

**注意**: 与官方版本不同，社区版本的 addon 不使用 `requests` 库，而是使用内置的 `urllib.request`。

## 4. 构建系统

### 4.1 Hatchling

- 使用 Hatchling 作为构建后端
- 现代化的 Python 打包工具
- 自动发现包

### 4.2 包布局

```
src/
└── blender_open_mcp/
    ├── __init__.py
    ├── server.py
    └── client_entry.py
```

### 4.3 入口点

```toml
[project.scripts]
blender-mcp = "blender_open_mcp.server:main"
blender-mcp-client = "client.client:main"
```

## 5. Python 版本

```
.python-version: 3.12.11
```

**注意**: pyproject.toml 声明 `>=3.10`，.python-version 指定 3.12.11。

## 6. 工具配置

### 6.1 pytest

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- 自动异步模式
- 无需手动标记异步测试

### 6.2 Ruff

```toml
[tool.ruff]
line-length = 100
```

- 行长度限制 100 字符

### 6.3 Mypy

```toml
[tool.mypy]
strict = false
```

- 非严格模式

## 7. 安装方式

### 7.1 作为 Python 包安装

```bash
# 使用 uv (推荐)
uv pip install -e .

# 或使用 pip
pip install -e .

# 安装可选依赖
pip install -e ".[client]"
pip install -e ".[dev]"
```

### 7.2 Blender 插件安装

1. 打开 Blender
2. Edit -> Preferences -> Add-ons
3. 点击 "Install..."
4. 选择 `addon.py` 文件
5. 启用 "Blender MCP" 插件

### 7.3 运行

```bash
# MCP Server
blender-mcp --transport stdio

# Client CLI
blender-mcp-client interactive

# 或
blender-mcp-client scene
```

## 8. 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BLENDER_HOST` | `localhost` | Blender addon 主机 |
| `BLENDER_PORT` | `9876` | Blender addon 端口 |
| `DEFAULT_OLLAMA_URL` | `http://localhost:11434` | Ollama URL |
| `DEFAULT_OLLAMA_MODEL` | `llama3.2` | 默认 Ollama 模型 |

## 9. 与官方版本的依赖差异

| 方面 | 官方版本 | 社区版本 |
|------|----------|----------|
| 构建系统 | setuptools | hatchling |
| MCP 框架 | mcp[cli]>=1.3.0 | mcp[cli]>=1.6.0 |
| HTTP 客户端 | requests (addon) | httpx (server) + urllib (addon) |
| 数据验证 | 无 | pydantic>=2.0.0 |
| 遥测 | supabase>=2.0.0 | 无 |
| TOML 解析 | tomli>=2.0.0 | 无 |
| 测试 | 无 | pytest, pytest-asyncio |
| Linting | 无 | ruff, mypy, black |
| 客户端 | 无 | httpx (可选) |
