# Blender MCP Official - 优劣势分析

## 优势

### 1. 丰富的外部集成
- **PolyHaven**: 完整的 HDRI/纹理/模型支持，包含完整 PBR 节点图
- **Sketchfab**: 搜索、预览、下载，含 zip-slip 安全保护
- **Hyper3D Rodin**: 文本/图片生成 3D 模型，支持双模式 (MAIN_SITE/FAL_AI)
- **Hunyuan3D**: 腾讯云 API + 本地 API 双模式

### 2. 成熟的 PBR 纹理设置
- 完整的 Principled BSDF 节点图
- 支持所有主要贴图通道: Base Color, Roughness, Metallic, Normal, Displacement, ARM, AO
- 正确的颜色空间设置 (sRGB vs Non-Color)

### 3. 视口截图功能
- 可以捕获 Blender 3D 视口的截图
- 支持尺寸限制和等比缩放
- 返回 Image 对象供 Claude 分析

### 4. 完善的模型导入
- 尺寸归一化（缩放到目标大小）
- Zip-slip 安全保护
- 空父节点清理
- 多格式支持 (glTF, FBX, OBJ, blend)

### 5. 遥测系统
- 匿名使用统计
- 用户同意感知
- 可通过环境变量禁用
- Supabase 后端

### 6. Asset Creation Strategy Prompt
- 指导 Claude 的资产创建工作流
- 优先级: Sketchfab > PolyHaven > Hyper3D > Hunyuan3D > 脚本回退

### 7. 持久连接
- 连接复用，减少连接建立开销
- 自动重连机制

### 8. 免费试用 API 密钥
- Hyper3D 提供内置免费试用密钥
- 降低初始使用门槛

## 劣势

### 1. 无输入验证
- 服务器端没有参数验证
- 直接将参数传递给 addon
- 缺少类型检查和范围验证

### 2. 无测试套件
- 没有单元测试
- 没有集成测试
- 难以验证功能正确性

### 3. 单文件过大
- addon.py 2636 行，难以维护
- 没有关注点分离
- 所有 handler、UI、服务器逻辑混在一起

### 4. 持久连接的脆弱性
- 连接验证使用 `get_polyhaven_status` 作为 ping
- 这个命令有副作用（实际执行状态检查）
- 如果 PolyHaven 禁用，连接验证会失败

### 5. 同步阻塞
- 所有 MCP 工具函数都是同步的
- 阻塞事件循环
- 影响并发性能

### 6. 安全问题
- `execute_blender_code` 执行任意代码，无沙箱
- 硬编码的 API 密钥 (`RODIN_FREE_TRIAL_KEY`)
- Supabase 凭证在配置文件中

### 7. 场景信息限制
- `get_scene_info` 静默限制为前 10 个对象
- 大型场景会丢失信息

### 8. Socket 接收逻辑
- 使用 JSON 解析作为分隔符（脆弱）
- 大型响应可能需要多次接收
- 没有明确的消息边界

### 9. 遥测依赖
- 依赖 Supabase（外部服务）
- 需要额外配置文件
- 增加了部署复杂性

### 10. 代码质量
- 没有类型注解
- 没有文档字符串
- 没有 linting 配置
- 没有 CI/CD

## 改进建议

### 高优先级
1. 添加 Pydantic 输入验证
2. 编写单元测试和集成测试
3. 拆分 addon.py 为多个模块
4. 使用 `bpy.app.timers.register` 的替代方案（更安全的线程调度）

### 中优先级
5. 移除硬编码凭证
6. 添加类型注解
7. 实现消息分隔符协议
8. 优化场景信息返回（分页或全量返回）

### 低优先级
9. 添加 CI/CD 流程
10. 实现代码执行沙箱
11. 添加 MCP 资源端点
12. 支持更多传输协议 (streamable_http)
