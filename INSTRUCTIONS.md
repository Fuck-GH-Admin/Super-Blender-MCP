# Blender MCP 使用指南

本项目通过 MCP 工具直接控制 Blender。**遇到 Blender 相关任务时，直接使用下方 MCP 工具，不要手动检查端口、进程或读源码。**

## 第一条规则：直接调工具

不要用 bash/netstat/Get-Process 检查 Blender 是否运行。直接调用 MCP 工具：

- `blender_get_scene_info` — 查看场景所有对象和状态（首选入口）
- `blender_get_object_info` — 查看具体对象的详细信息

## 可用工具速查

### 场景操作
- `blender_get_scene_info` — 全场景摘要（对象、相机、渲染设置）
- `blender_get_object_info` — 单个对象详细信息
- `blender_create_object` — 创建基本几何体
- `blender_modify_object` — 移动/旋转/缩放/显隐
- `blender_delete_object` — 删除对象
- `blender_set_material` — 设置材质颜色
- `blender_execute_code` — 执行自定义 bpy 代码（复杂材质、修改器等）
- `blender_render_image` — 渲染输出

### 3D 资源优先级（按顺序尝试）
1. `blender_search_sketchfab_models` — 搜索现有高质量模型
2. `blender_download_polyhaven_model` — 免费 CC0 模型
3. `blender_generate_hyper3d_model_via_text` — AI 生成模型
4. `blender_generate_hunyuan3d_model` — 腾讯 3D 生成
5. `blender_create_object` / `blender_execute_code` — 手工创建

### 其他工具
- `blender_get_viewport_screenshot` — 查看视口画面
- `blender_get_polyhaven_categories` / `blender_search_polyhaven_assets` — 浏览免费资产
- `blender_ai_prompt` — 让本地 Ollama 协助写 Blender 脚本
