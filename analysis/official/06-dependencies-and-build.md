# Blender MCP Official - 依赖与构建

## 1. 项目配置

**文件**: `pyproject.toml`

```toml
[project]
name = "blender-mcp"
version = "1.5.5"
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = [
    "mcp[cli]>=1.3.0",
    "supabase>=2.0.0",
    "tomli>=2.0.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]
```

## 2. Python 依赖

### 2.1 运行时依赖

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| `mcp[cli]` | >=1.3.0 | MCP 协议框架（含 CLI 扩展） |
| `supabase` | >=2.0.0 | Supabase 客户端（遥测数据上传） |
| `tomli` | >=2.0.0 | TOML 解析器（读取 pyproject.toml 版本） |

### 2.2 MCP 框架依赖链

```
mcp[cli]
├── mcp (核心协议)
├── anyio (异步 IO)
├── httpx (HTTP 客户端)
├── pydantic (数据验证)
└── typer (CLI 框架)
```

## 3. Blender 插件依赖

### 3.1 内置模块（无需安装）

| 模块 | 用途 |
|------|------|
| `bpy` | Blender Python API |
| `mathutils` | 数学工具（向量、矩阵） |
| `socket` | TCP 网络通信 |
| `threading` | 多线程 |
| `json` | JSON 序列化 |
| `io` | StringIO（stdout 捕获） |
| `os` | 文件系统操作 |
| `tempfile` | 临时文件 |
| `zipfile` | ZIP 解压 |
| `shutil` | 文件操作 |
| `hashlib` | 哈希算法 |
| `hmac` | HMAC 签名 |
| `base64` | Base64 编码 |
| `datetime` | 日期时间 |
| `traceback` | 异常追踪 |
| `time` | 时间操作 |
| `re` | 正则表达式 |

### 3.2 外部依赖（需安装）

| 包名 | 用途 |
|------|------|
| `requests` | HTTP 请求（PolyHaven, Sketchfab, Hyper3D, Hunyuan3D API） |

**注意**: `requests` 不在 pyproject.toml 中声明，需要在 Blender Python 环境中单独安装。

## 4. 构建系统

### 4.1 setuptools

- 使用 setuptools 作为构建后端
- 包布局: `src/blender_mcp/` (通过 `tool.setuptools.package-dir`)

### 4.2 入口点

```toml
[project.scripts]
blender-mcp = "blender_mcp.server:main"
```

### 4.3 锁文件

- `uv.lock`: uv 包管理器的锁文件
- 精确锁定所有依赖版本

## 5. Python 版本

```
.python-version: 3.13.2
```

**注意**: 虽然 pyproject.toml 声明 `>=3.10`，但 .python-version 指定了 3.13.2。

## 6. 安装方式

### 6.1 作为 Python 包安装

```bash
# 使用 uv (推荐)
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 6.2 Blender 插件安装

1. 打开 Blender
2. Edit -> Preferences -> Add-ons
3. 点击 "Install..."
4. 选择 `addon.py` 文件
5. 启用 "Blender MCP" 插件

### 6.3 运行 MCP Server

```bash
# 直接运行
blender-mcp

# 或通过 main.py
python main.py
```

## 7. 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BLENDER_HOST` | `localhost` | Blender addon 主机 |
| `BLENDER_PORT` | `9876` | Blender addon 端口 |
| `DISABLE_TELEMETRY` | - | 禁用遥测 |
| `BLENDER_MCP_DISABLE_TELEMETRY` | - | 禁用遥测 |
| `MCP_DISABLE_TELEMETRY` | - | 禁用遥测 |

## 8. 遥测配置

遥测需要 Supabase 配置文件 `src/blender_mcp/config.py`（已 gitignore）:

```python
supabase_url = "https://your-project.supabase.co"
supabase_anon_key = "your-anon-key"
```

**注意**: 此文件不包含在仓库中，需要自行创建。
