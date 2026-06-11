"""
Blender Super MCP Server
========================
FastMCP server that exposes Blender tools to Claude Code via MCP protocol.

Architecture:
  Claude Code ──stdio──> MCP Server ──TCP:9876──> Blender Addon
                            │                         │
                            │ httpx                   │ bpy API
                            v                         v
                         Ollama                   Blender 3D
"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
import socket
import sys
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Logging (stderr to not pollute stdio transport)
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("super_mcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
import os
BLENDER_HOST: str = os.environ.get("BLENDER_HOST", "127.0.0.1")
BLENDER_PORT: int = int(os.environ.get("BLENDER_PORT", "0"))  # 0 = auto-discover
BLENDER_TIMEOUT: float = 600.0  # 10 minutes for renders
BLENDER_PORT_SCAN_RANGE: tuple[int, int] = (9876, 9890)

DEFAULT_OLLAMA_URL: str = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL: str = "llama3.2"

POLYHAVEN_API_BASE: str = "https://api.polyhaven.com"

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
_state: Dict[str, Any] = {
    "ollama_url": DEFAULT_OLLAMA_URL,
    "ollama_model": DEFAULT_OLLAMA_MODEL,
}

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP("blender_super_mcp")


# ===========================================================================
# Auto-discovery
# ===========================================================================

def _discover_blender_port(host: str, scan_range: tuple[int, int]) -> int:
    """Scan TCP ports to find a running Blender MCP add-on. Returns the port or raises."""
    probe = json.dumps({"type": "get_scene_info", "params": {}}) + "\n"
    for port in range(scan_range[0], scan_range[1] + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((host, port))
            sock.sendall(probe.encode("utf-8"))
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
            sock.close()
            raw = b"".join(chunks).decode("utf-8").strip()
            resp = json.loads(raw)
            if resp.get("status") == "ok":
                logger.info("Auto-discovered Blender MCP on port %d", port)
                return port
        except (ConnectionRefusedError, TimeoutError, OSError, json.JSONDecodeError):
            continue
    raise ConnectionRefusedError(
        f"Could not find Blender MCP add-on on {host} ports {scan_range[0]}-{scan_range[1]}. "
        "Make sure Blender is open with the Super MCP add-on enabled and the server started "
        "(N-key sidebar → Super MCP → Start Server)."
    )


def _ensure_blender_port() -> None:
    """Auto-discover Blender port if not explicitly set."""
    global BLENDER_PORT
    if BLENDER_PORT == 0:
        BLENDER_PORT = _discover_blender_port(BLENDER_HOST, BLENDER_PORT_SCAN_RANGE)


# ===========================================================================
# Shared helpers
# ===========================================================================

def _send_blender_command(command_type: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Send a JSON command to the Blender add-on TCP server and return the parsed response.

    Each command is a newline-terminated JSON object:
        {"type": "<command_type>", "params": {...}}\n
    Response:
        {"status": "ok"|"error", "result": <any>, "message": "<error>"}
    """
    payload = json.dumps({"type": command_type, "params": params or {}}) + "\n"
    _ensure_blender_port()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(BLENDER_TIMEOUT)
        try:
            sock.connect((BLENDER_HOST, BLENDER_PORT))
            sock.sendall(payload.encode("utf-8"))
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks).decode("utf-8").strip()
        finally:
            sock.close()
        response: Dict[str, Any] = json.loads(raw)
        return response
    except ConnectionRefusedError:
        raise ConnectionRefusedError(
            f"Cannot connect to Blender add-on at {BLENDER_HOST}:{BLENDER_PORT}. "
            "Make sure Blender is open with the Super MCP add-on enabled and the server started "
            "(N-key sidebar → Super MCP → Start Server)."
        )
    except TimeoutError:
        raise TimeoutError(
            f"Blender add-on did not respond within {BLENDER_TIMEOUT}s. "
            "The operation may still be running in Blender."
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON response from Blender: {exc}. Raw: {raw!r}")


def _format_blender_result(response: Dict[str, Any]) -> str:
    """Convert a Blender TCP response into a human-readable string."""
    if response.get("status") == "error":
        return f"Error from Blender: {response.get('message', 'Unknown error')}"
    result = response.get("result", response)
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2)
    return str(result)


async def _query_ollama(prompt: str, system_prompt: str | None = None) -> str:
    """Send a prompt to the local Ollama server and return the response."""
    url = f"{_state['ollama_url']}/api/generate"
    payload: Dict[str, Any] = {
        "model": _state["ollama_model"],
        "prompt": prompt,
        "stream": False,
    }
    if system_prompt:
        payload["system"] = system_prompt
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except httpx.ConnectError:
            return (
                f"Error: Cannot connect to Ollama at {_state['ollama_url']}. "
                "Make sure Ollama is running: `ollama serve`."
            )
        except httpx.HTTPStatusError as exc:
            return f"Error: Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            return f"Error communicating with Ollama: {type(exc).__name__}: {exc}"


def _handle_blender_error(exc: Exception) -> str:
    """Produce a friendly error string from common exceptions."""
    if isinstance(exc, (ConnectionRefusedError, TimeoutError, ValueError)):
        return str(exc)
    return f"Unexpected error: {type(exc).__name__}: {exc}"


# ===========================================================================
# Input models (Pydantic v2)
# ===========================================================================

class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


class GetObjectInfoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    object_name: str = Field(..., description="Name of the Blender object", min_length=1, max_length=256)


class PrimitiveType(str, Enum):
    CUBE = "CUBE"
    SPHERE = "SPHERE"
    CYLINDER = "CYLINDER"
    CONE = "CONE"
    TORUS = "TORUS"
    PLANE = "PLANE"
    CIRCLE = "CIRCLE"
    ICO_SPHERE = "ICO_SPHERE"
    GRID = "GRID"
    MONKEY = "MONKEY"


class Vec3(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    x: float = Field(default=0.0, description="X coordinate")
    y: float = Field(default=0.0, description="Y coordinate")
    z: float = Field(default=0.0, description="Z coordinate")

    def as_list(self) -> List[float]:
        return [self.x, self.y, self.z]


class CreateObjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    primitive_type: PrimitiveType = Field(default=PrimitiveType.CUBE, description="Primitive mesh type")
    name: Optional[str] = Field(default=None, description="Object name", max_length=256)
    location: Optional[Vec3] = Field(default=None, description="World-space location {x, y, z}")
    rotation: Optional[Vec3] = Field(default=None, description="Euler rotation in radians {x, y, z}")
    scale: Optional[Vec3] = Field(default=None, description="Scale {x, y, z}")


class ModifyObjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    name: str = Field(..., description="Object name to modify", min_length=1, max_length=256)
    location: Optional[Vec3] = Field(default=None, description="New location {x, y, z}")
    rotation: Optional[Vec3] = Field(default=None, description="New rotation {x, y, z}")
    scale: Optional[Vec3] = Field(default=None, description="New scale {x, y, z}")
    visible: Optional[bool] = Field(default=None, description="Viewport visibility")


class DeleteObjectInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    name: str = Field(..., description="Object name to delete", min_length=1, max_length=256)


class SetMaterialInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    object_name: str = Field(..., description="Object name", min_length=1, max_length=256)
    material_name: str = Field(..., description="Material name", min_length=1, max_length=256)
    color: Optional[List[float]] = Field(default=None, description="RGBA color [R,G,B] or [R,G,B,A] in [0.0, 1.0]")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is None:
            return v
        if len(v) not in (3, 4):
            raise ValueError("color must be [R, G, B] or [R, G, B, A]")
        for c in v:
            if not (0.0 <= c <= 1.0):
                raise ValueError(f"Color channel {c} out of range [0.0, 1.0]")
        if len(v) == 3:
            v = v + [1.0]
        return v


class RenderImageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    file_path: str = Field(..., description="Absolute file path for render output", min_length=1, max_length=1024)


class ExecuteCodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    code: str = Field(..., description="Python code to execute in Blender", min_length=1)


class ViewportScreenshotInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    filepath: Optional[str] = Field(default=None, description="Output file path (auto-generated if None)")
    max_size: int = Field(default=800, ge=100, le=4096, description="Max dimension in pixels")
    format: str = Field(default="png", description="Image format: png, jpg")


class PolyHavenAssetType(str, Enum):
    HDRIs = "hdris"
    TEXTURES = "textures"
    MODELS = "models"
    ALL = "all"


class GetPolyHavenCategoriesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    asset_type: PolyHavenAssetType = Field(default=PolyHavenAssetType.TEXTURES, description="Asset type")


class SearchPolyHavenInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    asset_type: PolyHavenAssetType = Field(default=PolyHavenAssetType.TEXTURES, description="Asset type")
    categories: Optional[List[str]] = Field(default=None, description="Category filters")
    limit: int = Field(default=20, ge=1, le=100, description="Max results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class DownloadPolyHavenInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    asset_id: str = Field(..., description="PolyHaven asset ID", min_length=1, max_length=128)
    asset_type: PolyHavenAssetType = Field(default=PolyHavenAssetType.TEXTURES, description="Asset type")
    resolution: str = Field(default="1k", description="Resolution: 1k, 2k, 4k, 8k")
    file_format: str = Field(default="jpg", description="File format: jpg, png, exr, hdr, blend, gltf")


class SetTextureInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    object_name: str = Field(..., description="Object to texture", min_length=1, max_length=256)
    texture_id: str = Field(..., description="Downloaded texture asset ID", min_length=1, max_length=128)


class DownloadPolyHavenModelInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    asset_id: str = Field(..., description="PolyHaven model asset ID", min_length=1, max_length=128)
    resolution: str = Field(default="1k", description="Resolution")
    file_format: str = Field(default="gltf", description="Format: gltf, glb, fbx, obj, blend")


class SearchSketchfabInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    query: str = Field(..., description="Search query", min_length=1, max_length=256)
    categories: Optional[str] = Field(default=None, description="Category filter")
    count: int = Field(default=20, ge=1, le=100, description="Max results")
    downloadable: bool = Field(default=True, description="Only downloadable models")


class SketchfabUidInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    uid: str = Field(..., description="Sketchfab model UID", min_length=1, max_length=128)


class DownloadSketchfabInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    uid: str = Field(..., description="Sketchfab model UID", min_length=1, max_length=128)
    normalize_size: bool = Field(default=False, description="Normalize model size")
    target_size: float = Field(default=1.0, gt=0, description="Target size in meters")


class Hyper3DCreateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    text_prompt: Optional[str] = Field(default=None, description="Text prompt for 3D generation")
    images: Optional[List[List[str]]] = Field(default=None, description="Images as [[suffix, base64], ...]")
    bbox_condition: Optional[Dict] = Field(default=None, description="Bounding box condition")


class Hyper3DPollInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    subscription_key: Optional[str] = Field(default=None, description="Main site subscription key")
    request_id: Optional[str] = Field(default=None, description="fal.ai request ID")


class Hyper3DImportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    task_uuid: Optional[str] = Field(default=None, description="Main site task UUID")
    request_id: Optional[str] = Field(default=None, description="fal.ai request ID")
    name: Optional[str] = Field(default=None, description="Name for imported object")


class Hunyuan3DGenerateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    text_prompt: Optional[str] = Field(default=None, description="Text prompt")
    image: Optional[str] = Field(default=None, description="Image path or URL")


class Hunyuan3DPollInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    job_id: str = Field(..., description="Hunyuan3D job ID", min_length=1)


class Hunyuan3DImportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    zip_file_url: str = Field(..., description="URL of the model zip file", min_length=1)
    name: Optional[str] = Field(default=None, description="Name for imported object")


class SetOllamaModelInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    model_name: str = Field(..., description="Ollama model name", min_length=1, max_length=128)


class SetOllamaUrlInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    url: str = Field(..., description="Ollama server URL", min_length=1, max_length=512)


class PromptInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
    prompt: str = Field(..., description="Natural language prompt", min_length=1)
    system_prompt: Optional[str] = Field(default=None, description="Custom system prompt")


# ===========================================================================
# MCP Tools - Core (Scene & Objects)
# ===========================================================================

@mcp.tool(
    name="blender_get_scene_info",
    annotations={"title": "Get Scene Info", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_get_scene_info() -> str:
    """Get a full summary of the current Blender scene: all objects, camera, frame range, render settings."""
    try:
        response = _send_blender_command("get_scene_info")
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_get_object_info",
    annotations={"title": "Get Object Info", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_get_object_info(params: GetObjectInfoInput) -> str:
    """Get detailed info about a specific Blender object: transform, mesh stats, materials, lights, cameras."""
    try:
        response = _send_blender_command("get_object_info", {"object_name": params.object_name})
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_create_object",
    annotations={"title": "Create 3D Object", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False},
)
async def blender_create_object(params: CreateObjectInput) -> str:
    """Create a new primitive mesh in Blender. Supports: CUBE, SPHERE, CYLINDER, CONE, TORUS, PLANE, CIRCLE, ICO_SPHERE, GRID, MONKEY."""
    cmd_params: Dict[str, Any] = {"type": params.primitive_type.value}
    if params.name:
        cmd_params["name"] = params.name
    if params.location:
        cmd_params["location"] = params.location.as_list()
    if params.rotation:
        cmd_params["rotation"] = params.rotation.as_list()
    if params.scale:
        cmd_params["scale"] = params.scale.as_list()
    try:
        response = _send_blender_command("create_object", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_modify_object",
    annotations={"title": "Modify Object", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_modify_object(params: ModifyObjectInput) -> str:
    """Modify an existing object's location, rotation, scale, or visibility. Only provided fields are updated."""
    cmd_params: Dict[str, Any] = {"name": params.name}
    if params.location:
        cmd_params["location"] = params.location.as_list()
    if params.rotation:
        cmd_params["rotation"] = params.rotation.as_list()
    if params.scale:
        cmd_params["scale"] = params.scale.as_list()
    if params.visible is not None:
        cmd_params["visible"] = params.visible
    try:
        response = _send_blender_command("modify_object", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_delete_object",
    annotations={"title": "Delete Object", "readOnlyHint": False, "destructiveHint": True,
                 "idempotentHint": False, "openWorldHint": False},
)
async def blender_delete_object(params: DeleteObjectInput) -> str:
    """Permanently delete an object from the Blender scene. Use get_scene_info first to confirm the name."""
    try:
        response = _send_blender_command("delete_object", {"name": params.name})
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - Materials & Rendering
# ===========================================================================

@mcp.tool(
    name="blender_set_material",
    annotations={"title": "Set Material", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_material(params: SetMaterialInput) -> str:
    """Create/reuse a Principled BSDF material and assign it to an object. Optionally set base color."""
    cmd_params: Dict[str, Any] = {"object_name": params.object_name, "material_name": params.material_name}
    if params.color:
        cmd_params["color"] = params.color
    try:
        response = _send_blender_command("set_material", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_render_image",
    annotations={"title": "Render Image", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_render_image(params: RenderImageInput) -> str:
    """Render the current Blender scene to a file. Uses the scene's current render engine and camera."""
    try:
        response = _send_blender_command("render_image", {"file_path": params.file_path})
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - Code Execution
# ===========================================================================

@mcp.tool(
    name="blender_execute_code",
    annotations={"title": "Execute Python Code", "readOnlyHint": False, "destructiveHint": True,
                 "idempotentHint": False, "openWorldHint": False},
)
async def blender_execute_code(params: ExecuteCodeInput) -> str:
    """Execute arbitrary Python code inside Blender (bpy module). Use for operations not covered by other tools."""
    try:
        response = _send_blender_command("execute_code", {"code": params.code})
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - Viewport Screenshot
# ===========================================================================

@mcp.tool(
    name="blender_get_viewport_screenshot",
    annotations={"title": "Viewport Screenshot", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False},
)
async def blender_get_viewport_screenshot(params: ViewportScreenshotInput) -> str:
    """Capture a screenshot of the 3D viewport. Returns the file path and dimensions."""
    cmd_params: Dict[str, Any] = {"max_size": params.max_size, "format": params.format}
    if params.filepath:
        cmd_params["filepath"] = params.filepath
    try:
        response = _send_blender_command("get_viewport_screenshot", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - PolyHaven
# ===========================================================================

@mcp.tool(
    name="blender_get_polyhaven_categories",
    annotations={"title": "PolyHaven Categories", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_get_polyhaven_categories(params: GetPolyHavenCategoriesInput) -> str:
    """List available asset categories from PolyHaven (free CC0 HDRIs, textures, models)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{POLYHAVEN_API_BASE}/categories/{params.asset_type.value}")
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


@mcp.tool(
    name="blender_search_polyhaven_assets",
    annotations={"title": "Search PolyHaven", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_search_polyhaven_assets(params: SearchPolyHavenInput) -> str:
    """Search PolyHaven assets by type and category. Returns paginated results with asset IDs."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            query: Dict[str, Any] = {"type": params.asset_type.value}
            if params.categories:
                query["categories"] = ",".join(params.categories)
            resp = await client.get(f"{POLYHAVEN_API_BASE}/assets", params=query)
            resp.raise_for_status()
            all_assets: Dict[str, Any] = resp.json()

        items = list(all_assets.items())
        total = len(items)
        page = items[params.offset: params.offset + params.limit]
        result = {
            "total": total,
            "count": len(page),
            "offset": params.offset,
            "has_more": total > params.offset + len(page),
            "items": [{"id": k, **v} for k, v in page],
        }
        return json.dumps(result, indent=2)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


@mcp.tool(
    name="blender_download_polyhaven_asset",
    annotations={"title": "Download PolyHaven Asset", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_download_polyhaven_asset(params: DownloadPolyHavenInput) -> str:
    """Download a PolyHaven asset into Blender. For HDRIs: sets world environment. For textures: stores for set_texture."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{POLYHAVEN_API_BASE}/files/{params.asset_id}")
            resp.raise_for_status()
            files_data: Dict[str, Any] = resp.json()
    except Exception as exc:
        return f"Error fetching asset info: {type(exc).__name__}: {exc}"

    try:
        cmd_params: Dict[str, Any] = {
            "asset_id": params.asset_id,
            "asset_type": params.asset_type.value,
            "resolution": params.resolution,
            "file_format": params.file_format,
            "files_data": files_data,
        }
        response = _send_blender_command("download_polyhaven_asset", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_set_texture",
    annotations={"title": "Apply Texture to Object", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_texture(params: SetTextureInput) -> str:
    """Apply a previously downloaded PolyHaven texture to an object with full PBR node graph."""
    try:
        response = _send_blender_command("set_texture", {
            "object_name": params.object_name,
            "texture_id": params.texture_id,
        })
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_download_polyhaven_model",
    annotations={"title": "Download PolyHaven Model", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_download_polyhaven_model(params: DownloadPolyHavenModelInput) -> str:
    """Download and import a 3D model from PolyHaven. Supports gltf, glb, fbx, obj, blend."""
    try:
        response = _send_blender_command("download_polyhaven_model", {
            "asset_id": params.asset_id,
            "resolution": params.resolution,
            "file_format": params.file_format,
        })
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - Sketchfab
# ===========================================================================

@mcp.tool(
    name="blender_get_sketchfab_status",
    annotations={"title": "Sketchfab Status", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_get_sketchfab_status() -> str:
    """Check if Sketchfab integration is enabled and API key is valid."""
    try:
        response = _send_blender_command("get_sketchfab_status")
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_search_sketchfab_models",
    annotations={"title": "Search Sketchfab", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_search_sketchfab_models(params: SearchSketchfabInput) -> str:
    """Search for 3D models on Sketchfab. Requires API key configured in Blender panel."""
    try:
        response = _send_blender_command("search_sketchfab_models", {
            "query": params.query,
            "categories": params.categories,
            "count": params.count,
            "downloadable": params.downloadable,
        })
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_get_sketchfab_model_preview",
    annotations={"title": "Sketchfab Preview", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_get_sketchfab_model_preview(params: SketchfabUidInput) -> str:
    """Get a thumbnail preview of a Sketchfab model. Returns base64-encoded image data."""
    try:
        response = _send_blender_command("get_sketchfab_model_preview", {"uid": params.uid})
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_download_sketchfab_model",
    annotations={"title": "Download Sketchfab Model", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_download_sketchfab_model(params: DownloadSketchfabInput) -> str:
    """Download and import a model from Sketchfab. Optional size normalization."""
    try:
        response = _send_blender_command("download_sketchfab_model", {
            "uid": params.uid,
            "normalize_size": params.normalize_size,
            "target_size": params.target_size,
        })
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - Hyper3D Rodin
# ===========================================================================

@mcp.tool(
    name="blender_get_hyper3d_status",
    annotations={"title": "Hyper3D Status", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_get_hyper3d_status() -> str:
    """Check Hyper3D Rodin integration status and configuration."""
    try:
        response = _send_blender_command("get_hyper3d_status")
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_generate_hyper3d_model_via_text",
    annotations={"title": "Hyper3D Text-to-3D", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": True},
)
async def blender_generate_hyper3d_model_via_text(params: Hyper3DCreateInput) -> str:
    """Generate a 3D model from text prompt using Hyper3D Rodin."""
    cmd_params: Dict[str, Any] = {}
    if params.text_prompt:
        cmd_params["text_prompt"] = params.text_prompt
    if params.images:
        cmd_params["images"] = params.images
    if params.bbox_condition:
        cmd_params["bbox_condition"] = params.bbox_condition
    try:
        response = _send_blender_command("create_rodin_job", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_generate_hyper3d_model_via_images",
    annotations={"title": "Hyper3D Image-to-3D", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": True},
)
async def blender_generate_hyper3d_model_via_images(params: Hyper3DCreateInput) -> str:
    """Generate a 3D model from images using Hyper3D Rodin. Images should be [[suffix, base64], ...]."""
    cmd_params: Dict[str, Any] = {}
    if params.text_prompt:
        cmd_params["text_prompt"] = params.text_prompt
    if params.images:
        cmd_params["images"] = params.images
    if params.bbox_condition:
        cmd_params["bbox_condition"] = params.bbox_condition
    try:
        response = _send_blender_command("create_rodin_job", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_poll_rodin_job_status",
    annotations={"title": "Poll Rodin Job", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_poll_rodin_job_status(params: Hyper3DPollInput) -> str:
    """Poll the status of a Hyper3D Rodin generation job."""
    cmd_params: Dict[str, Any] = {}
    if params.subscription_key:
        cmd_params["subscription_key"] = params.subscription_key
    if params.request_id:
        cmd_params["request_id"] = params.request_id
    try:
        response = _send_blender_command("poll_rodin_job_status", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_import_generated_asset",
    annotations={"title": "Import Hyper3D Asset", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False},
)
async def blender_import_generated_asset(params: Hyper3DImportInput) -> str:
    """Import a completed Hyper3D Rodin generation into Blender."""
    cmd_params: Dict[str, Any] = {}
    if params.task_uuid:
        cmd_params["task_uuid"] = params.task_uuid
    if params.request_id:
        cmd_params["request_id"] = params.request_id
    if params.name:
        cmd_params["name"] = params.name
    try:
        response = _send_blender_command("import_generated_asset", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - Hunyuan3D
# ===========================================================================

@mcp.tool(
    name="blender_get_hunyuan3d_status",
    annotations={"title": "Hunyuan3D Status", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_get_hunyuan3d_status() -> str:
    """Check Hunyuan3D integration status and configuration."""
    try:
        response = _send_blender_command("get_hunyuan3d_status")
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_generate_hunyuan3d_model",
    annotations={"title": "Generate Hunyuan3D Model", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": True},
)
async def blender_generate_hunyuan3d_model(params: Hunyuan3DGenerateInput) -> str:
    """Generate a 3D model using Hunyuan3D (Tencent). Provide either text_prompt or image."""
    cmd_params: Dict[str, Any] = {}
    if params.text_prompt:
        cmd_params["text_prompt"] = params.text_prompt
    if params.image:
        cmd_params["image"] = params.image
    try:
        response = _send_blender_command("generate_hunyuan3d_model", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_poll_hunyuan_job_status",
    annotations={"title": "Poll Hunyuan3D Job", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_poll_hunyuan_job_status(params: Hunyuan3DPollInput) -> str:
    """Poll the status of a Hunyuan3D generation job."""
    try:
        response = _send_blender_command("poll_hunyuan_job_status", {"job_id": params.job_id})
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


@mcp.tool(
    name="blender_import_generated_asset_hunyuan",
    annotations={"title": "Import Hunyuan3D Asset", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": False},
)
async def blender_import_generated_asset_hunyuan(params: Hunyuan3DImportInput) -> str:
    """Import a completed Hunyuan3D generation (zip with OBJ) into Blender."""
    cmd_params: Dict[str, Any] = {"zip_file_url": params.zip_file_url}
    if params.name:
        cmd_params["name"] = params.name
    try:
        response = _send_blender_command("import_generated_asset_hunyuan", cmd_params)
        return _format_blender_result(response)
    except Exception as exc:
        return _handle_blender_error(exc)


# ===========================================================================
# MCP Tools - Ollama
# ===========================================================================

@mcp.tool(
    name="blender_ai_prompt",
    annotations={"title": "AI Prompt (Ollama)", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": False, "openWorldHint": True},
)
async def blender_ai_prompt(params: PromptInput) -> str:
    """Send a natural language prompt to the local Ollama model. Useful for Blender scripting help."""
    system = params.system_prompt or (
        "You are an expert Blender 3D artist and Python developer. "
        "You help users control Blender using the bpy Python API. "
        "Provide concise, runnable Python code examples when appropriate. "
        f"Current Ollama model: {_state['ollama_model']}."
    )
    return await _query_ollama(params.prompt, system_prompt=system)


@mcp.tool(
    name="blender_set_ollama_model",
    annotations={"title": "Set Ollama Model", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_ollama_model(params: SetOllamaModelInput) -> str:
    """Switch the Ollama model. Must already be pulled (ollama pull <model>)."""
    _state["ollama_model"] = params.model_name
    return f"Ollama model set to: {params.model_name}"


@mcp.tool(
    name="blender_set_ollama_url",
    annotations={"title": "Set Ollama URL", "readOnlyHint": False, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
async def blender_set_ollama_url(params: SetOllamaUrlInput) -> str:
    """Update the Ollama server URL."""
    _state["ollama_url"] = params.url
    return f"Ollama URL set to: {params.url}"


@mcp.tool(
    name="blender_get_ollama_models",
    annotations={"title": "List Ollama Models", "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": True},
)
async def blender_get_ollama_models() -> str:
    """List all locally available Ollama models."""
    url = f"{_state['ollama_url']}/api/tags"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            models = [
                {"name": m.get("name"), "size_gb": round(m.get("size", 0) / 1e9, 2), "modified_at": m.get("modified_at", "")}
                for m in data.get("models", [])
            ]
            return json.dumps({"current_model": _state["ollama_model"], "available_models": models}, indent=2)
        except httpx.ConnectError:
            return f"Error: Cannot connect to Ollama at {_state['ollama_url']}."
        except Exception as exc:
            return f"Error: {type(exc).__name__}: {exc}"


# ===========================================================================
# MCP Prompt - Asset Creation Strategy
# ===========================================================================

@mcp.prompt()
def asset_creation_strategy() -> str:
    """Guide Claude's asset creation workflow with priority ordering."""
    return """When creating 3D assets in Blender, follow this priority order:

1. **Check Sketchfab** - Search for existing high-quality models first
   - Use blender_search_sketchfab_models to find models
   - Use blender_get_sketchfab_model_preview to preview
   - Use blender_download_sketchfab_model to import

2. **Check PolyHaven** - Free CC0 textures, HDRIs, and models
   - Use blender_get_polyhaven_categories to browse
   - Use blender_search_polyhaven_assets to find assets
   - Use blender_download_polyhaven_asset to download
   - Use blender_set_texture to apply with full PBR

3. **Check Hyper3D Rodin** - AI-generated 3D models
   - Use blender_generate_hyper3d_model_via_text or via_images
   - Use blender_poll_rodin_job_status to check progress
   - Use blender_import_generated_asset to import

4. **Check Hunyuan3D** - Tencent's 3D generation
   - Use blender_generate_hunyuan3d_model
   - Use blender_poll_hunyuan_job_status to check progress
   - Use blender_import_generated_asset_hunyuan to import

5. **Fallback to code** - Use blender_execute_code for custom creation
   - Use blender_create_object for basic primitives
   - Use blender_set_material for materials
"""


# ===========================================================================
# Entry point
# ===========================================================================

def main() -> None:
    """CLI entry point."""
    global BLENDER_HOST, BLENDER_PORT

    parser = argparse.ArgumentParser(
        prog="blender-super-mcp",
        description="Blender Super MCP: Unified MCP server for Blender3D.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="FastMCP server host (HTTP mode)")
    parser.add_argument("--port", type=int, default=8000, help="FastMCP server port (HTTP mode)")
    parser.add_argument("--blender-host", default=BLENDER_HOST, help="Blender add-on TCP host")
    parser.add_argument("--blender-port", type=int, default=0, help="Blender add-on TCP port (0 = auto-discover)")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama server URL")
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL, help="Default Ollama model")
    parser.add_argument(
        "--transport",
        choices=["streamable_http", "stdio"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args()

    BLENDER_HOST = args.blender_host
    BLENDER_PORT = args.blender_port
    _state["ollama_url"] = args.ollama_url
    _state["ollama_model"] = args.ollama_model

    logger.info("Starting Blender Super MCP server")
    logger.info("  Transport     : %s", args.transport)
    if args.transport == "streamable_http":
        logger.info("  Endpoint      : http://%s:%d", args.host, args.port)
    if BLENDER_PORT == 0:
        logger.info("  Blender add-on: %s (auto-discover on first command)", BLENDER_HOST)
    else:
        logger.info("  Blender add-on: %s:%d", BLENDER_HOST, BLENDER_PORT)
    logger.info("  Ollama URL    : %s", _state["ollama_url"])
    logger.info("  Ollama model  : %s", _state["ollama_model"])

    if args.transport == "streamable_http":
        mcp.run(transport="streamable_http", host=args.host, port=args.port)
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    main()
