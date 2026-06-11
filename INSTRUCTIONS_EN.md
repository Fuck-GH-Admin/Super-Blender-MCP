# Blender MCP Usage Guide

This project controls Blender directly via MCP tools. **When asked to do something in Blender, use the MCP tools below directly — do NOT manually check ports, processes, or read source code.**

## Rule #1: Use Tools Directly

Do NOT use bash/netstat/Get-Process to check if Blender is running. Call MCP tools directly:

- `blender_get_scene_info` — View the full scene with all objects and state (primary entry point)
- `blender_get_object_info` — Get detailed info about a specific object

## Available Tools Cheatsheet

### Scene Operations
- `blender_get_scene_info` — Full scene summary (objects, camera, render settings)
- `blender_get_object_info` — Detailed object info
- `blender_create_object` — Create basic primitives
- `blender_modify_object` — Move/rotate/scale/toggle visibility
- `blender_delete_object` — Delete an object
- `blender_set_material` — Set material color
- `blender_execute_code` — Run custom bpy code (complex materials, modifiers, etc.)
- `blender_render_image` — Render output
- `blender_get_viewport_screenshot` — See what the viewport looks like

### 3D Asset Priority (try in order)
1. `blender_search_sketchfab_models` — Search existing high-quality models
2. `blender_download_polyhaven_model` — Free CC0 models
3. `blender_generate_hyper3d_model_via_text` — AI-generated models
4. `blender_generate_hunyuan3d_model` — Tencent 3D generation
5. `blender_create_object` / `blender_execute_code` — Manual creation

### External Integrations
- `blender_get_polyhaven_categories` / `blender_search_polyhaven_assets` — Browse free assets
- `blender_download_polyhaven_asset` / `blender_set_texture` — Download & apply PBR textures
- `blender_get_sketchfab_status` / `blender_search_sketchfab_models` — Sketchfab (API key needed)
- `blender_get_hyper3d_status` / `blender_generate_hyper3d_model_via_text` — Hyper3D Rodin AI

### AI Assistance
- `blender_ai_prompt` — Ask the local Ollama model for Blender scripting help
