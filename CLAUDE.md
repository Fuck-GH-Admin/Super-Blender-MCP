# CLAUDE.md - Blender Super MCP

This project is a Blender MCP server that lets you control Blender 3D via natural language.

## How It Works

Three processes:
- **You (Claude Code)** talk to the MCP server over stdio
- **MCP Server** (`superMCP/mcp_server.py`) forwards commands to Blender over TCP
- **Blender Addon** (`superMCP/addon.py`) executes commands using the bpy API

The server auto-discovers Blender's port (scans 9876-9890) on first command.

## Key Tools

### Core (Scene & Objects)

| Tool | When to Use |
|------|-------------|
| `blender_get_scene_info` | First thing: understand what's in the scene |
| `blender_get_object_info` | Need details on a specific object (mesh stats, modifiers, materials) |
| `blender_create_object` | Add primitives (CUBE, SPHERE, CYLINDER, TORUS, MONKEY, etc.) |
| `blender_modify_object` | Move, rotate, scale, toggle visibility |
| `blender_delete_object` | Remove an object |
| `blender_set_material` | Simple material with color (Principled BSDF) |
| `blender_execute_code` | Complex materials, modifiers, particle systems, geometry nodes -- anything the built-in tools can't do |
| `blender_render_image` | Render final image |
| `blender_get_viewport_screenshot` | See what the viewport looks like |

### PolyHaven (Free CC0 Assets)

| Tool | When to Use |
|------|-------------|
| `blender_get_polyhaven_categories` | Browse available categories (hdris/textures/models) |
| `blender_search_polyhaven_assets` | Search PolyHaven by type and category |
| `blender_download_polyhaven_asset` | Download HDRI or texture into Blender |
| `blender_set_texture` | Apply a downloaded texture with full PBR node graph |
| `blender_download_polyhaven_model` | Download and import a 3D model (gltf/glb/fbx/obj/blend) |

### Sketchfab (API Key Required)

| Tool | When to Use |
|------|-------------|
| `blender_get_sketchfab_status` | Check if Sketchfab is configured and API key is valid |
| `blender_search_sketchfab_models` | Search for 3D models on Sketchfab |
| `blender_get_sketchfab_model_preview` | Get thumbnail preview (returns base64 image) |
| `blender_download_sketchfab_model` | Download and import a Sketchfab model |

### Hyper3D Rodin (AI 3D Generation)

| Tool | When to Use |
|------|-------------|
| `blender_get_hyper3d_status` | Check Hyper3D configuration |
| `blender_generate_hyper3d_model_via_text` | Generate 3D model from text prompt |
| `blender_generate_hyper3d_model_via_images` | Generate 3D model from images |
| `blender_poll_rodin_job_status` | Poll generation job progress |
| `blender_import_generated_asset` | Import completed generation into scene |

### Hunyuan3D (Tencent AI 3D Generation)

| Tool | When to Use |
|------|-------------|
| `blender_get_hunyuan3d_status` | Check Hunyuan3D configuration |
| `blender_generate_hunyuan3d_model` | Generate 3D model from text or image |
| `blender_poll_hunyuan_job_status` | Poll generation job progress |
| `blender_import_generated_asset_hunyuan` | Import completed generation (zip with OBJ) |

### Ollama (Local LLM)

| Tool | When to Use |
|------|-------------|
| `blender_ai_prompt` | Ask the local Ollama model for Blender scripting help |
| `blender_set_ollama_model` | Switch Ollama model |
| `blender_set_ollama_url` | Change Ollama server URL |
| `blender_get_ollama_models` | List available Ollama models |

## Common Workflows

### Create and position an object
```
blender_create_object(primitive_type="SPHERE", name="MySphere", location={"x": 2, "y": 0, "z": 0})
```

### Change material (simple)
```
blender_set_material(object_name="Cube", material_name="RedMat", color=[0.8, 0.2, 0.2, 1.0])
```

### Complex material (glass, crystal, emission, etc.)
Use `blender_execute_code` with full bpy script. Example for glass:
```python
import bpy
mat = bpy.data.materials.new(name="Glass")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Transmission Weight"].default_value = 1.0
bsdf.inputs["IOR"].default_value = 1.45
bsdf.inputs["Roughness"].default_value = 0.05
obj = bpy.context.active_object
obj.data.materials[0] = mat
```

### Download and apply a PBR texture from PolyHaven
```
blender_download_polyhaven_asset(asset_id="rock_boulder", asset_type="textures", resolution="2k")
blender_set_texture(object_name="Cube", texture_id="rock_boulder")
```

### Generate 3D model with AI
```
blender_generate_hunyuan3d_model(text_prompt="a small wooden chair")
blender_poll_hunyuan_job_status(job_id="<returned_job_id>")
blender_import_generated_asset_hunyuan(zip_file_url="<url_from_poll>", name="Chair")
```

### Priority order for creating 3D assets

When you need a 3D model, follow this priority:

1. **Sketchfab** — Search existing high-quality models (API key required)
   - `blender_search_sketchfab_models` → preview with `blender_get_sketchfab_model_preview` → `blender_download_sketchfab_model`

2. **PolyHaven** — Free CC0 assets
   - `blender_get_polyhaven_categories` / `blender_search_polyhaven_assets` → `blender_download_polyhaven_asset` / `blender_download_polyhaven_model` → `blender_set_texture`

3. **Hyper3D Rodin** — AI-generated 3D from text/images
   - `blender_generate_hyper3d_model_via_text` / `via_images` → `blender_poll_rodin_job_status` → `blender_import_generated_asset`

4. **Hunyuan3D** — Tencent AI 3D generation
   - `blender_generate_hunyuan3d_model` → `blender_poll_hunyuan_job_status` → `blender_import_generated_asset_hunyuan`

5. **Code / Primitives** — Last resort: build from scratch
   - `blender_create_object` for primitives → `blender_set_material` / `blender_execute_code` for custom materials & geometry

### Check scene before making changes
Always call `blender_get_scene_info` first to understand what objects exist and their state.

### Performance optimization
If the scene is laggy:
- Reduce Cycles preview samples: `scene.cycles.preview_samples = 64`
- Add Decimate modifier to high-poly objects
- Reduce particle display percentage: `settings.display_percentage = 5`
- Lower max bounces: `scene.cycles.max_bounces = 6`

## Important Notes

- **Blender version**: Addon targets Blender 3.0+. Some APIs differ across versions:
  - `Transmission Weight` (4.0+) was `Transmission` in 3.x
  - `shadow_method` removed in 4.0; use `blend_method = 'HASHED'` for transparency
- **Viewport vs Render**: Use Light Path nodes to switch between fast viewport and full-quality render materials.
- **MCP server port**: Auto-discovered. No need to specify `--blender-port` unless you want to pin it.
- **First command may be slow**: Auto-discovery scans ports 9876-9890, takes a few seconds.
- **External integrations** (Sketchfab, Hyper3D, Hunyuan3D) need API keys configured in the Blender sidebar panel.
- **Thread safety**: All commands run on Blender's main thread via a timer queue. Do NOT access `bpy.context.active_object` directly in handler code — use `bpy.data.objects` iteration instead.
- **Auto-start**: The TCP server starts automatically when the addon is registered. No need to manually click "Start Server".
- **Recv buffer**: The addon now uses a buffered recv loop (up to 1MB) instead of a single `recv()` call, preventing request truncation.
- **Property names**: All scene properties use the `supermcp_*` prefix (NOT `blendermcp_*`). External integrations read from the correct registered properties.

## File Structure

```
superMCP/
  mcp_server.py         # MCP server (FastMCP, connects to Claude Code via stdio)
  addon.py              # Blender addon (TCP server, executes bpy commands)
  pyproject.toml        # Python package config
  requirements.txt      # Python dependencies (httpx, mcp, pydantic)
  test_blender_connection.py  # Connection test script
  test_echo_server.py         # Echo server for testing
analysis/               # Comparison docs (Chinese)
blender-mcp-official/   # Original ahujasid BlenderMCP
blender-mcp-community/  # Community blender-open-mcp
USAGE.md                # Usage guide
```
