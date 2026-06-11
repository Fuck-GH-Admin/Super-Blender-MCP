# Blender Super MCP

Control Blender 3D from opencode or Claude Code via natural language. Combines the best of the official (ahujasid) and community (blender-open-mcp) versions.

## Architecture

```
opencode/Claude Code ──stdio──> MCP Server ──TCP:9876──> Blender Addon
                                    │                         │
                                    │ httpx                   │ bpy API
                                    v                         v
                                 Ollama                   Blender 3D
```

- **MCP Server** (`superMCP/mcp_server.py`): FastMCP server via stdio
- **Blender Addon** (`superMCP/addon.py`): TCP server inside Blender, executes bpy commands on the main thread
- **Ollama** (optional): Local LLM for AI prompts

## Quick Start

### 1. Install the Addon in Blender

1. Open Blender → Edit → Preferences → Add-ons
2. Click the dropdown → "Install from Disk" → select `superMCP/addon.py`
3. Enable "Blender Super MCP"
4. The TCP server auto-starts when the addon is enabled. In 3D Viewport, press N → Super MCP to see the status.

### 2. Configure opencode / Claude Code

**opencode** (auto via project config):
The `opencode.json` in this repo already defines the MCP server — just open the project.

**Claude Code:**
```bash
claude mcp add --transport stdio blender -- python /absolute/path/to/superMCP/mcp_server.py
```

### 3. Use It

Ask your AI assistant to control Blender:
- "Create a red cube at position (1, 0, 0)"
- "Set up an HDRI from PolyHaven"
- "Search Sketchfab for a car model"

## Available Tools (31)

### Core (8)
| Tool | Description |
|------|-------------|
| `blender_get_scene_info` | Full scene summary |
| `blender_get_object_info` | Detailed object info (mesh stats, modifiers, materials) |
| `blender_create_object` | Create primitives (CUBE, SPHERE, CYLINDER, TORUS, MONKEY, etc.) |
| `blender_modify_object` | Move, rotate, scale, toggle visibility |
| `blender_delete_object` | Delete objects |
| `blender_set_material` | Set/create materials with Principled BSDF color |
| `blender_render_image` | Render to file |
| `blender_execute_code` | Execute Python code for complex materials, modifiers, geometry nodes, etc. |

### Viewport (1)
| Tool | Description |
|------|-------------|
| `blender_get_viewport_screenshot` | Capture 3D viewport screenshot |

### PolyHaven (5)
| Tool | Description |
|------|-------------|
| `blender_get_polyhaven_categories` | List categories (hdris/textures/models) |
| `blender_search_polyhaven_assets` | Search assets by type and category |
| `blender_download_polyhaven_asset` | Download HDRI/texture into Blender |
| `blender_set_texture` | Apply PBR texture with full node graph |
| `blender_download_polyhaven_model` | Download and import a 3D model (gltf/glb/fbx/obj/blend) |

### Sketchfab (API Key Required) (4)
| Tool | Description |
|------|-------------|
| `blender_get_sketchfab_status` | Check integration and API key validity |
| `blender_search_sketchfab_models` | Search for 3D models |
| `blender_get_sketchfab_model_preview` | Get thumbnail preview (base64 image) |
| `blender_download_sketchfab_model` | Download and import model |

### Hyper3D Rodin (AI 3D Generation) (5)
| Tool | Description |
|------|-------------|
| `blender_get_hyper3d_status` | Check Hyper3D configuration |
| `blender_generate_hyper3d_model_via_text` | Text-to-3D generation |
| `blender_generate_hyper3d_model_via_images` | Image-to-3D generation |
| `blender_poll_rodin_job_status` | Poll generation job progress |
| `blender_import_generated_asset` | Import completed generation into scene |

### Hunyuan3D (Tencent AI 3D Generation) (4)
| Tool | Description |
|------|-------------|
| `blender_get_hunyuan3d_status` | Check Hunyuan3D configuration |
| `blender_generate_hunyuan3d_model` | Generate 3D model from text or image |
| `blender_poll_hunyuan_job_status` | Poll generation job progress |
| `blender_import_generated_asset_hunyuan` | Import completed generation (zip with OBJ) |

### Ollama (Local LLM) (4)
| Tool | Description |
|------|-------------|
| `blender_ai_prompt` | Send natural language prompt for Blender scripting help |
| `blender_set_ollama_model` | Switch Ollama model |
| `blender_set_ollama_url` | Change Ollama server URL |
| `blender_get_ollama_models` | List available Ollama models |

## Key Fixes & Improvements

- **Thread safety**: All commands run on Blender's main thread via a timer queue — eliminates `Context` errors from TCP threads
- **Auto-start server**: TCP server starts automatically when the addon is registered; no manual "Start Server" needed
- **Robust TCP receive**: Fixed single `recv()` truncation — now uses buffered loop with JSON validation; tested with 628KB payloads
- **External integrations fixed**: 26 instances of incorrect `blendermcp_*` property names fixed to `supermcp_*` — Sketchfab, Hyper3D, and Hunyuan3D now work correctly

## CLI Options

```
python superMCP/mcp_server.py [OPTIONS]

  --transport {stdio,streamable_http}  MCP transport (default: stdio)
  --host HOST                          HTTP server host
  --port PORT                          HTTP server port
  --blender-host HOST                  Blender TCP host (default: localhost)
  --blender-port PORT                  Blender TCP port (default: 9876)
  --ollama-url URL                     Ollama server URL
  --ollama-model MODEL                 Default Ollama model
```

## License

MIT
