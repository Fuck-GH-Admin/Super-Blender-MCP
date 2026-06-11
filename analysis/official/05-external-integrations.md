# Blender MCP Official - 外部集成

## 1. PolyHaven

### 1.1 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `https://api.polyhaven.com/categories/{asset_type}` | GET | 获取分类 |
| `https://api.polyhaven.com/assets` | GET | 搜索资产 |
| `https://api.polyhaven.com/files/{asset_id}` | GET | 获取下载链接 |

- User-Agent: `"blender-mcp"`

### 1.2 HDRI 导入

创建世界节点树:
```
TexCoord (UV) -> Mapping -> Environment Texture -> Background -> Output World
```

- 颜色空间: Linear
- 投影方式: Equirectangular

### 1.3 纹理导入

创建 Principled BSDF 材质，包含以下贴图通道:

| 贴图类型 | 节点连接 | 颜色空间 |
|----------|----------|----------|
| Diffuse/Base Color | Base Color | sRGB |
| Roughness | Roughness | Non-Color |
| Metallic | Metallic | Non-Color |
| Normal | Normal Map -> Normal | Non-Color |
| Displacement | Displacement | Non-Color |
| ARM (AO+Rough+Metal) | 通过分离节点 | Non-Color |
| AO | Ambient Occlusion | Non-Color |

**实现**: addon.py lines 560-750

### 1.4 模型导入

- 支持格式: glTF (.glb/.gltf), FBX, OBJ, blend
- 下载包含文件 (include files)
- 使用对应的 Blender 导入操作符

---

## 2. Hyper3D Rodin

### 2.1 双模式架构

**MAIN_SITE 模式**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `https://hyperhuman.deemos.com/api/v2/rodin` | POST | 创建生成任务 |
| `https://hyperhuman.deemos.com/api/v2/status` | POST | 查询状态 |
| `https://hyperhuman.deemos.com/api/v2/download` | POST | 下载结果 |

- 认证: Bearer Token

**FAL_AI 模式**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `https://queue.fal.run/fal-ai/hyper3d/rodin` | POST | 创建生成任务 |
| `https://queue.fal.run/fal-ai/hyper3d/rodin/{request_id}` | GET | 查询状态 |
| `https://queue.fal.run/fal-ai/hyper3d/rodin/{request_id}` | GET | 下载结果 |

- 认证: Key

### 2.2 免费试用密钥

```python
RODIN_FREE_TRIAL_KEY = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"
```

### 2.3 bbox_condition 处理

```python
# 归一化为整数，最大比例 100
if bbox_condition:
    max_val = max(bbox_condition)
    bbox_condition = [int(v / max_val * 100) for v in bbox_condition]
```

### 2.4 工作流

```
1. generate_hyper3d_model_via_text/images -> task_uuid + subscription_key
2. poll_rodin_job_status -> 状态检查
3. import_generated_asset -> 下载 GLB -> bpy.ops.import_scene.gltf
```

---

## 3. Sketchfab

### 3.1 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `https://api.sketchfab.com/v3/search` | GET | 搜索模型 |
| `https://api.sketchfab.com/v3/models/{uid}` | GET | 获取模型信息 |
| `https://api.sketchfab.com/v3/models/{uid}/download` | GET | 获取下载链接 |

### 3.2 认证

```python
headers = {"Authorization": f"Token {api_key}"}
```

### 3.3 下载流程

```
1. search_sketchfab_models -> 获取 uid 列表
2. get_sketchfab_model_preview -> 获取缩略图
3. download_sketchfab_model:
   a. 获取下载 URL
   b. 下载 ZIP
   c. 安全检查 (zip-slip protection)
   d. 解压
   e. glTF 导入
   f. 尺寸归一化
```

### 3.4 Zip-slip 安全保护

```python
for member in zip_ref.infolist():
    # 防止路径遍历攻击
    if '..' in member.filename or member.filename.startswith('/'):
        continue
    # 检查解压路径是否在目标目录内
    target_path = os.path.join(extract_dir, member.filename)
    if not os.path.abspath(target_path).startswith(os.path.abspath(extract_dir)):
        continue
```

### 3.5 尺寸归一化

```python
# 计算当前包围盒大小
bbox = get_bounding_box(obj)
current_size = max(bbox.dimensions)

# 计算缩放因子
scale_factor = target_size / current_size

# 应用缩放
obj.scale = (scale_factor, scale_factor, scale_factor)
bpy.ops.object.transform_apply(scale=True)
```

---

## 4. Hunyuan3D

### 4.1 OFFICIAL_API (腾讯云)

**API 端点**: `hunyuan.tencentcloudapi.com`

**签名算法**: TC3-HMAC-SHA256

**请求参数**:
- Service: "hunyuan"
- Region: "ap-guangzhou"
- Actions:
  - `SubmitHunyuanTo3DJob`: 提交生成任务
  - `QueryHunyuanTo3DJob`: 查询任务状态

**限制**:
- 文本提示最大 200 字符

**签名生成** (`get_tencent_cloud_sign_headers`):
```python
# 1. 规范请求
canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

# 2. 待签名字符串
string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{service}/tc3_request\n{hash(canonical_request)}"

# 3. 签名
secret_date = hmac("TC3" + secret_key, date)
secret_service = hmac(secret_date, service)
secret_signing = hmac(secret_service, "tc3_request")
signature = hmac(secret_signing, string_to_sign).hexdigest()
```

### 4.2 LOCAL_API

**默认端点**: `http://localhost:8081/generate`

**请求参数**:
- `octree_resolution`: 八叉树分辨率 (128-512, 默认 256)
- `num_inference_steps`: 推理步数 (20-50, 默认 20)
- `guidance_scale`: 引导比例 (1.0-10.0, 默认 5.5)
- `texture`: 是否生成纹理 (默认 False)

**响应**: 直接返回 GLB 文件

### 4.3 工作流

**OFFICIAL_API**:
```
1. generate_hunyuan3d_model -> job_id
2. poll_hunyuan_job_status -> 状态检查
3. import_generated_asset_hunyuan:
   a. 下载 ZIP
   b. 提取 OBJ
   c. bpy.ops.wm.obj_import (Blender 4.0+)
      或 bpy.ops.import_scene.obj (Blender <4.0)
```

**LOCAL_API**:
```
1. generate_hunyuan3d_model -> 直接返回 GLB
2. import_generated_asset_hunyuan -> 导入
```

---

## 5. Telemetry (Supabase)

### 5.1 事件类型

| 事件 | 说明 |
|------|------|
| `STARTUP` | 服务器启动 |
| `TOOL_EXECUTION` | 工具执行 |
| `PROMPT_SENT` | Prompt 发送 |
| `CONNECTION` | 连接事件 |
| `ERROR` | 错误事件 |

### 5.2 数据字段

| 字段 | 说明 |
|------|------|
| `customer_uuid` | 匿名用户 ID |
| `session_id` | 会话 ID |
| `tool_name` | 工具名称 |
| `success` | 是否成功 |
| `duration_ms` | 执行时间 (毫秒) |
| `platform` | 平台 |
| `version` | 版本 |

### 5.3 同意机制

- 检查 Blender 偏好设置中的 `blendermcp_telemetry_consent`
- 无同意时: 剥离 prompts、metadata、error details
- 仅记录: 工具名、成功/失败、持续时间

### 5.4 禁用方式

```bash
export DISABLE_TELEMETRY=1
# 或
export BLENDER_MCP_DISABLE_TELEMETRY=1
# 或
export MCP_DISABLE_TELEMETRY=1
```
