# Blender Super MCP - Usage Guide

## What Is This

Blender Super MCP lets you control Blender from Claude Code through natural language. Ask Claude to create objects, change materials, set up scenes, render, and more -- all without touching Blender's UI.

## Quick Setup

### 1. Install Python Dependencies

```bash
pip install "mcp[cli]>=1.6.0" "fastmcp>=2.0.0" "httpx>=0.27.0" "pydantic>=2.0.0"
```

### 2. Install Blender Addon

1. Open Blender -> Edit -> Preferences -> Add-ons
2. Click **Install** -> select `superMCP/addon.py`
3. Enable **"Blender Super MCP"**

### 3. Start Server in Blender

1. In 3D Viewport, press **N** to open sidebar
2. Go to **Super MCP** tab
3. Click **Start Server**
4. Note the port number shown (usually 9876)

### 4. Register MCP Server with Claude Code

```bash
claude mcp add --transport stdio blender -- python /absolute/path/to/superMCP/mcp_server.py
```

The server auto-discovers which port Blender is on (scans 9876-9890), so you don't need to specify the port.

If you need to specify a port explicitly:

```bash
claude mcp add --transport stdio blender -- python /path/to/mcp_server.py --blender-port 9880
```

### 5. Use It

Open Claude Code in this project directory and ask:

- "Get the current Blender scene info"
- "Create a red sphere at (2, 0, 0)"
- "Make the cube use a glass material"
- "Render the scene"

## CLI Options

```
python mcp_server.py [OPTIONS]

  --transport {stdio,streamable_http}  MCP transport (default: stdio)
  --host HOST                          HTTP server host (default: 0.0.0.0)
  --port PORT                          HTTP server port (default: 8000)
  --blender-host HOST                  Blender TCP host (default: 127.0.0.1)
  --blender-port PORT                  Blender TCP port (0 = auto-discover, default: 0)
  --ollama-url URL                     Ollama server URL
  --ollama-model MODEL                 Default Ollama model
```

Environment variables: `BLENDER_HOST`, `BLENDER_PORT`

## Available Tools (31)

### Scene Query
| Tool | Description |
|------|-------------|
| `blender_get_scene_info` | Full scene: all objects, camera, frame range, render settings |
| `blender_get_object_info` | Detailed info: transforms, mesh stats, materials, modifiers |
| `blender_get_viewport_screenshot` | Capture 3D viewport as image |

### Object Operations
| Tool | Description |
|------|-------------|
| `blender_create_object` | Create primitives: CUBE, SPHERE, CYLINDER, CONE, TORUS, PLANE, MONKEY, etc. |
| `blender_modify_object` | Change location, rotation, scale, visibility |
| `blender_delete_object` | Delete an object |
| `blender_set_material` | Create/assign Principled BSDF material with RGBA color |
| `blender_render_image` | Render the scene to a file |
| `blender_execute_code` | Execute arbitrary bpy Python code (escape hatch) |

### PolyHaven (free PBR assets)
| Tool | Description |
|------|-------------|
| `blender_get_polyhaven_categories` | List asset categories |
| `blender_search_polyhaven_assets` | Search textures, HDRIs, models |
| `blender_download_polyhaven_asset` | Download HDRI/texture |
| `blender_set_texture` | Apply full PBR texture node graph |
| `blender_download_polyhaven_model` | Download 3D model (glTF, FBX, OBJ, blend) |

### Sketchfab
| Tool | Description |
|------|-------------|
| `blender_get_sketchfab_status` | Check API key status |
| `blender_search_sketchfab_models` | Search models |
| `blender_get_sketchfab_model_preview` | Get thumbnail |
| `blender_download_sketchfab_model` | Download and import model |

### Hyper3D Rodin (AI 3D generation)
| Tool | Description |
|------|-------------|
| `blender_get_hyper3d_status` | Check integration |
| `blender_generate_hyper3d_model_via_text` | Text-to-3D |
| `blender_generate_hyper3d_model_via_images` | Image-to-3D |
| `blender_poll_rodin_job_status` | Poll generation job |
| `blender_import_generated_asset` | Import result |

### Hunyuan3D (Tencent AI 3D)
| Tool | Description |
|------|-------------|
| `blender_get_hunyuan3d_status` | Check integration |
| `blender_generate_hunyuan3d_model` | Generate 3D model |
| `blender_poll_hunyuan_job_status` | Poll generation job |
| `blender_import_generated_asset_hunyuan` | Import result |

### Ollama (local LLM)
| Tool | Description |
|------|-------------|
| `blender_ai_prompt` | Send prompt to local Ollama |
| `blender_set_ollama_model` | Switch model |
| `blender_set_ollama_url` | Set server URL |
| `blender_get_ollama_models` | List available models |

## Tips

- **Viewport mode matters**: Use Material Preview or Rendered mode in Blender to see material changes
- **Cycles vs EEVEE**: Complex materials (glass, volume, transmission) look best in Cycles
- **Performance**: If Blender gets laggy, reduce viewport samples, add Decimate modifiers, or hide heavy particle systems
- **Execute code**: For anything the built-in tools can't do, `blender_execute_code` runs arbitrary Python in Blender

## Architecture

```
Claude Code  --stdio-->  MCP Server (mcp_server.py)  --TCP-->  Blender Addon (addon.py)
                              |                                     |
                              | httpx                               | bpy API
                              v                                     v
                           Ollama                               Blender 3D
```

The MCP server and Blender addon communicate via newline-terminated JSON over TCP.
The server auto-discovers Blender's port on first command (scans 9876-9890).
