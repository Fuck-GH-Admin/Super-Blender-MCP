# Blender Super MCP - Installation Guide

## Prerequisites

- **Blender** 3.0 or newer
- **Python** 3.10 or newer
- **Claude Code** CLI or desktop app
- **Ollama** (optional, for AI prompts)

## Step 1: Install Python Dependencies

```bash
pip install "mcp[cli]>=1.6.0" "fastmcp>=2.0.0" "httpx>=0.27.0" "pydantic>=2.0.0"
```

## Step 2: Install the Blender Addon

1. Open Blender
2. Go to **Edit → Preferences → Add-ons**
3. Click **Install...** (top right)
4. Navigate to `superMCP/addon.py` and select it
5. Enable the addon by checking **"Interface: Blender Super MCP"**

## Step 3: Start the Addon Server in Blender

1. In the 3D Viewport, press **N** to open the sidebar
2. Find the **"Super MCP"** tab
3. Click **"Start Server"**
4. You should see "Server Running" with port 9876

### Configure Integrations (optional)

In the Super MCP panel, you can enable:
- **Poly Haven**: Free CC0 textures, HDRIs, and models
- **Hyper3D Rodin**: AI 3D generation (needs API key)
- **Sketchfab**: 3D model library (needs API key)
- **Hunyuan 3D**: Tencent's 3D generation (needs API key or local server)

## Step 4: Configure Claude Code

### Option A: Using `claude mcp add` (recommended)

```bash
claude mcp add --transport stdio blender -- python /absolute/path/to/superMCP/mcp_server.py
```

### Option B: Manual configuration

Add to `.claude/settings.json`:
```json
{
  "mcpServers": {
    "blender": {
      "command": "python",
      "args": ["/absolute/path/to/superMCP/mcp_server.py"]
    }
  }
}
```

### Option C: HTTP mode (for non-Claude-Code clients)

```bash
python mcp_server.py --transport streamable_http --port 8000
```

## Step 5: Test

In Claude Code, try:
```
Get the current Blender scene info
```

If it works, you'll see a list of objects in your Blender scene.

## Troubleshooting

### "Cannot connect to Blender add-on"
- Make sure Blender is open with the addon enabled
- Make sure you clicked "Start Server" in the Super MCP panel
- Check that port 9876 is not blocked

### "Invalid JSON response"
- The addon may have crashed. Check Blender's console for errors
- Restart the addon server

### External integrations not working
- PolyHaven: No API key needed, just enable in panel
- Sketchfab: Get API key from sketchfab.com → Settings → API Keys
- Hyper3D: Use free trial key (button in panel) or get your own
- Hunyuan3D: Need Tencent Cloud credentials or local Hunyuan3D server

### Ollama not responding
```bash
# Make sure Ollama is running
ollama serve

# Pull a model
ollama pull llama3.2
```

## Optional: Ollama Setup

Ollama provides local AI capabilities (no cloud API needed):

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2

# Start the server
ollama serve
```

The MCP server connects to Ollama at `http://localhost:11434` by default. Change with `--ollama-url`.
