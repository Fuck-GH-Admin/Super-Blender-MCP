# Blender Super MCP

Unified Blender MCP server combining the best of the official (ahujasid) and community (blender-open-mcp) versions. Directly control Blender from Claude Code via the Model Context Protocol.

## Architecture

```
Claude Code ──stdio──> MCP Server ──TCP:9876──> Blender Addon
                          │                         │
                          │ httpx                   │ bpy API
                          v                         v
                       Ollama                   Blender 3D
```

- **MCP Server** (`mcp_server.py`): FastMCP server, connects to Claude Code via stdio
- **Blender Addon** (`addon.py`): TCP server inside Blender, executes bpy commands
- **Ollama** (optional): Local LLM for AI prompts

## Quick Start

### 1. Install the Addon in Blender

1. Open Blender → Edit → Preferences → Add-ons
2. Click "Install" → select `addon.py`
3. Enable "Blender Super MCP"
4. In 3D Viewport, press N → Super MCP → Start Server

### 2. Configure Claude Code

```bash
claude mcp add --transport stdio blender -- python /absolute/path/to/superMCP/mcp_server.py
```

### 3. Use

Ask Claude Code to control Blender:
- "Create a red cube at position (1, 0, 0)"
- "Set up an HDRI from PolyHaven"
- "Search Sketchfab for a car model"

## Available Tools (31)

### Core (8)
| Tool | Description |
|------|-------------|
| `blender_get_scene_info` | Full scene summary |
| `blender_get_object_info` | Detailed object info |
| `blender_create_object` | Create primitives |
| `blender_modify_object` | Modify transforms |
| `blender_delete_object` | Delete objects |
| `blender_set_material` | Set/create materials |
| `blender_render_image` | Render to file |
| `blender_execute_code` | Execute Python code |

### Viewport (1)
| Tool | Description |
|------|-------------|
| `blender_get_viewport_screenshot` | Capture 3D viewport |

### PolyHaven (5)
| Tool | Description |
|------|-------------|
| `blender_get_polyhaven_categories` | List categories |
| `blender_search_polyhaven_assets` | Search assets |
| `blender_download_polyhaven_asset` | Download HDRI/texture |
| `blender_set_texture` | Apply PBR texture |
| `blender_download_polyhaven_model` | Download 3D model |

### Sketchfab (4)
| Tool | Description |
|------|-------------|
| `blender_get_sketchfab_status` | Check integration |
| `blender_search_sketchfab_models` | Search models |
| `blender_get_sketchfab_model_preview` | Get thumbnail |
| `blender_download_sketchfab_model` | Download model |

### Hyper3D Rodin (5)
| Tool | Description |
|------|-------------|
| `blender_get_hyper3d_status` | Check integration |
| `blender_generate_hyper3d_model_via_text` | Text-to-3D |
| `blender_generate_hyper3d_model_via_images` | Image-to-3D |
| `blender_poll_rodin_job_status` | Poll job |
| `blender_import_generated_asset` | Import result |

### Hunyuan3D (4)
| Tool | Description |
|------|-------------|
| `blender_get_hunyuan3d_status` | Check integration |
| `blender_generate_hunyuan3d_model` | Generate 3D |
| `blender_poll_hunyuan_job_status` | Poll job |
| `blender_import_generated_asset_hunyuan` | Import result |

### Ollama (4)
| Tool | Description |
|------|-------------|
| `blender_ai_prompt` | Send AI prompt |
| `blender_set_ollama_model` | Switch model |
| `blender_set_ollama_url` | Set server URL |
| `blender_get_ollama_models` | List models |

## MCP Prompt

- `asset_creation_strategy`: Guides Claude to check Sketchfab → PolyHaven → Hyper3D → Hunyuan3D → code fallback

## CLI Options

```
python mcp_server.py [OPTIONS]

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
