"""
Blender Add-on: Blender Super MCP (Unified)
============================================
Combines the official BlenderMCP (ahujasid) and community blender-open-mcp
into a single, best-of-both-worlds add-on for use with Claude Code.

Install:
  Edit -> Preferences -> Add-ons -> Install -> select addon.py -> enable "Blender Super MCP"

After enabling, open the 3D Viewport, press N, find the "Super MCP" panel,
and click "Start Server". The add-on listens on TCP port 9876 by default.

Protocol (JSON over TCP, newline-terminated):
  Request : {"type": "<command>", "params": {...}}\n
  Response: {"status": "ok", "result": <any>}\n
           {"status": "error", "message": "<reason>"}\n
"""

bl_info = {
    "name": "Blender Super MCP",
    "author": "Blender Super MCP contributors",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Super MCP",
    "description": "Unified MCP server add-on: control Blender via the Model Context Protocol",
    "category": "Interface",
}

import bpy
import bmesh
import json
import math
import os
import socket
import threading
import time
import traceback
import tempfile
import shutil
import zipfile
import io
import re
import sys
import hashlib
import hmac
import base64
import urllib.request
from datetime import datetime
from contextlib import redirect_stdout, suppress
from typing import Any, Dict, Optional
import mathutils

# Optional: requests (needed for external API integrations)
try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9876
SOCKET_TIMEOUT = 60.0
RECV_BUFFER = 8192

RODIN_FREE_TRIAL_KEY = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"

# User-Agent for API requests
_REQ_HEADERS = {"User-Agent": "blender-super-mcp"}


# ---------------------------------------------------------------------------
# Global server state
# ---------------------------------------------------------------------------
_server_socket: Optional[socket.socket] = None
_server_thread: Optional[threading.Thread] = None
_server_running = False

# Cross-reload stop signal: a temp file that tells old server loops to exit
_STOP_FILE = os.path.join(tempfile.gettempdir(), "blender_super_mcp_stop")


def _check_stop_file() -> bool:
    """Check if a stop signal file exists (for cross-reload shutdown)."""
    return os.path.exists(_STOP_FILE)


def _create_stop_file():
    """Create stop signal file to shut down old server loops."""
    try:
        with open(_STOP_FILE, "w") as f:
            f.write("stop")
    except Exception:
        pass


def _remove_stop_file():
    """Remove stop signal file."""
    try:
        os.remove(_STOP_FILE)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(result: Any) -> bytes:
    """Encode a successful response."""
    return (json.dumps({"status": "ok", "result": result}) + "\n").encode("utf-8")


def _err(message: str) -> bytes:
    """Encode an error response."""
    return (json.dumps({"status": "error", "message": message}) + "\n").encode("utf-8")


def _vec3_from_list(lst, default=(0.0, 0.0, 0.0)):
    """Convert a list/dict to a 3-tuple of floats."""
    if lst is None:
        return default
    if isinstance(lst, dict):
        return (float(lst.get("x", default[0])), float(lst.get("y", default[1])), float(lst.get("z", default[2])))
    if len(lst) >= 3:
        return tuple(float(v) for v in lst[:3])
    return default


def _get_aabb(obj):
    """Return the world-space axis-aligned bounding box of a mesh object."""
    if obj.type != 'MESH':
        raise TypeError("Object must be a mesh")
    local_bbox_corners = [mathutils.Vector(corner) for corner in obj.bound_box]
    world_bbox_corners = [obj.matrix_world @ corner for corner in local_bbox_corners]
    min_corner = mathutils.Vector(map(min, zip(*world_bbox_corners)))
    max_corner = mathutils.Vector(map(max, zip(*world_bbox_corners)))
    return [[*min_corner], [*max_corner]]


def _http_get_json(url, timeout=20):
    """Fetch JSON from a URL using urllib (no requests dependency)."""
    req = urllib.request.Request(url, headers=_REQ_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url, data=None, headers=None, timeout=30):
    """POST JSON using urllib."""
    payload = json.dumps(data).encode("utf-8") if data else b""
    hdrs = dict(_REQ_HEADERS)
    if headers:
        hdrs.update(headers)
    hdrs["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_download(url, dest_path, timeout=60):
    """Download a file from url to dest_path."""
    req = urllib.request.Request(url, headers=_REQ_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        with open(dest_path, "wb") as f:
            f.write(resp.read())


# ---------------------------------------------------------------------------
# Command handlers - Scene & Objects
# ---------------------------------------------------------------------------

def handle_get_scene_info(_params: Dict) -> Any:
    scene = bpy.context.scene
    objects = []
    for obj in scene.objects:
        objects.append({
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation_euler": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "visible_viewport": obj.visible_get(),
            "material_slots": [ms.name for ms in obj.material_slots],
        })
    camera = scene.camera.name if scene.camera else None
    return {
        "scene_name": scene.name,
        "frame_current": scene.frame_current,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "render_engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "active_camera": camera,
        "object_count": len(scene.objects),
        "objects": objects,
    }


def handle_get_object_info(params: Dict) -> Any:
    name = params.get("object_name", "")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found in the scene.")
    info: Dict[str, Any] = {
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation_euler": [math.degrees(r) for r in obj.rotation_euler],
        "rotation_euler_rad": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "visible_viewport": obj.visible_get(),
        "hide_render": obj.hide_render,
        "material_slots": [ms.name for ms in obj.material_slots],
        "parent": obj.parent.name if obj.parent else None,
        "children": [c.name for c in obj.children],
    }
    if obj.type == "MESH" and obj.data:
        info["vertex_count"] = len(obj.data.vertices)
        info["edge_count"] = len(obj.data.edges)
        info["polygon_count"] = len(obj.data.polygons)
        info["world_bounding_box"] = _get_aabb(obj)
    if obj.type == "LIGHT" and obj.data:
        info["light_type"] = obj.data.type
        info["light_energy"] = obj.data.energy
        info["light_color"] = list(obj.data.color)
    if obj.type == "CAMERA" and obj.data:
        info["camera_type"] = obj.data.type
        info["focal_length"] = obj.data.lens
    return info


def handle_create_object(params: Dict) -> Any:
    prim_type = params.get("type", params.get("primitive_type", "CUBE")).upper()
    location = _vec3_from_list(params.get("location"))
    rotation = _vec3_from_list(params.get("rotation"))
    scale = _vec3_from_list(params.get("scale"), (1.0, 1.0, 1.0))

    existing = set(bpy.data.objects.keys())

    prim_dispatch = {
        "CUBE":       bpy.ops.mesh.primitive_cube_add,
        "SPHERE":     bpy.ops.mesh.primitive_uv_sphere_add,
        "CYLINDER":   bpy.ops.mesh.primitive_cylinder_add,
        "CONE":       bpy.ops.mesh.primitive_cone_add,
        "TORUS":      bpy.ops.mesh.primitive_torus_add,
        "PLANE":      bpy.ops.mesh.primitive_plane_add,
        "CIRCLE":     bpy.ops.mesh.primitive_circle_add,
        "ICO_SPHERE": bpy.ops.mesh.primitive_ico_sphere_add,
        "GRID":       bpy.ops.mesh.primitive_grid_add,
        "MONKEY":     bpy.ops.mesh.primitive_monkey_add,
    }
    op = prim_dispatch.get(prim_type)
    if op is None:
        raise ValueError(f"Unknown primitive type '{prim_type}'. Valid: {list(prim_dispatch)}")

    op(location=location, rotation=rotation, scale=scale)

    new_objects = [bpy.data.objects[name] for name in bpy.data.objects.keys() if name not in existing]
    if not new_objects:
        raise RuntimeError("Object was not created after operator.")
    obj = new_objects[0]

    desired_name = params.get("name")
    if desired_name:
        obj.name = desired_name
        if obj.data:
            obj.data.name = desired_name

    return {
        "created": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation_euler": list(obj.rotation_euler),
        "scale": list(obj.scale),
    }


def handle_modify_object(params: Dict) -> Any:
    name = params.get("name", "")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found.")

    changed: Dict[str, Any] = {}

    loc = params.get("location")
    if loc is not None:
        obj.location = _vec3_from_list(loc)
        changed["location"] = list(obj.location)

    rot = params.get("rotation")
    if rot is not None:
        obj.rotation_euler = _vec3_from_list(rot)
        changed["rotation_euler"] = list(obj.rotation_euler)

    scl = params.get("scale")
    if scl is not None:
        obj.scale = _vec3_from_list(scl, (1.0, 1.0, 1.0))
        changed["scale"] = list(obj.scale)

    visible = params.get("visible")
    if visible is not None:
        obj.hide_viewport = not bool(visible)
        changed["visible_viewport"] = bool(visible)

    return {"modified": name, "changes": changed}


def handle_delete_object(params: Dict) -> Any:
    name = params.get("name", "")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found.")
    bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": name}


# ---------------------------------------------------------------------------
# Command handlers - Materials
# ---------------------------------------------------------------------------

def handle_set_material(params: Dict) -> Any:
    obj_name = params.get("object_name", "")
    mat_name = params.get("material_name", "")
    color = params.get("color")

    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        raise ValueError(f"Object '{obj_name}' not found.")
    if obj.type not in ("MESH", "CURVE", "SURFACE", "FONT", "META"):
        raise ValueError(f"Object '{obj_name}' is of type '{obj.type}' which does not support materials.")

    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes

    bsdf = nodes.get("Principled BSDF") or next(
        (n for n in nodes if n.type == "BSDF_PRINCIPLED"), None
    )
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")

    if color and len(color) >= 3:
        rgba = list(color) + [1.0] if len(color) == 3 else list(color[:4])
        bsdf.inputs["Base Color"].default_value = rgba

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return {"material_assigned": mat_name, "object": obj_name, "color": color}


# ---------------------------------------------------------------------------
# Command handlers - Rendering
# ---------------------------------------------------------------------------

import queue as _queue

# Queue for dispatching code execution to the main thread
_code_exec_queue: "_queue.Queue" = _queue.Queue()

# Generic command queue for thread-safe handler dispatch
_main_thread_cmd_queue: "_queue.Queue" = _queue.Queue()


def _main_thread_command_processor():
    """Timer callback that drains the generic command queue on the main thread."""
    while not _main_thread_cmd_queue.empty():
        try:
            handler, params, result_holder, done_event = _main_thread_cmd_queue.get_nowait()
        except _queue.Empty:
            break
        try:
            result = handler(params)
            result_holder["result"] = result
        except Exception as exc:
            result_holder["error"] = traceback.format_exc()
        done_event.set()
    return 0.05


def _main_thread_code_executor():
    """Timer callback that drains the code execution queue on Blender's main thread."""
    try:
        while not _code_exec_queue.empty():
            try:
                code, result_holder, done_event = _code_exec_queue.get_nowait()
            except _queue.Empty:
                break

            stdout_capture = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = stdout_capture
                local_ns: Dict[str, Any] = {"bpy": bpy}
                exec(compile(code, "<blender_mcp>", "exec"), local_ns)
                output = stdout_capture.getvalue()
            except Exception:
                output = traceback.format_exc()
            finally:
                sys.stdout = old_stdout

            result_holder["output"] = output or "(no output)"
            result_holder["code_length"] = len(code)
            done_event.set()
    except Exception:
        pass
    return 0.05  # re-register every 50ms


def handle_render_image(params: Dict) -> Any:
    file_path = params.get("file_path", "/tmp/blender_render.png")
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        raise ValueError(f"Directory '{directory}' does not exist. Please create it first.")

    escaped_path = repr(file_path)
    code = f"""
import bpy
scene = bpy.context.scene
scene.render.filepath = {escaped_path}
bpy.ops.render.render(write_still=True)
print("RENDER_DONE:" + {escaped_path})
"""
    result_holder: Dict[str, Any] = {}
    done_event = threading.Event()
    _code_exec_queue.put((code, result_holder, done_event))

    # Ensure the timer is running
    if not bpy.app.timers.is_registered(_main_thread_code_executor):
        bpy.app.timers.register(_main_thread_code_executor, first_interval=0.05)

    # Wait for render to complete (renders can take a while)
    done_event.wait(timeout=600)

    if not done_event.is_set():
        raise TimeoutError("Render timed out after 600 seconds")

    output = result_holder.get("output", "")
    if "RENDER_DONE" in output:
        scene = bpy.context.scene
        return {"rendered_to": file_path, "engine": scene.render.engine}
    else:
        raise RuntimeError(f"Render failed: {output}")


def handle_execute_code(params: Dict) -> Any:
    code = params.get("code", "")
    if not code.strip():
        raise ValueError("No code provided.")

    if not bpy.app.timers.is_registered(_main_thread_code_executor):
        bpy.app.timers.register(_main_thread_code_executor, first_interval=0.05)

    result_holder: Dict[str, Any] = {}
    done_event = threading.Event()
    _code_exec_queue.put((code, result_holder, done_event))

    # Wait for the main thread to process (with timeout)
    if not done_event.wait(timeout=120.0):
        raise TimeoutError("Code execution timed out (120s)")

    return result_holder


# ---------------------------------------------------------------------------
# Command handlers - Viewport Screenshot (from official)
# ---------------------------------------------------------------------------

def handle_get_viewport_screenshot(params: Dict) -> Any:
    filepath = params.get("filepath", "")
    max_size = params.get("max_size", 800)
    fmt = params.get("format", "png")

    if not filepath:
        filepath = os.path.join(tempfile.gettempdir(), f"viewport_screenshot.{fmt}")

    try:
        area = None
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                area = a
                break
        if not area:
            return {"error": "No 3D viewport found"}

        with bpy.context.temp_override(area=area):
            bpy.ops.screen.screenshot_area(filepath=filepath)

        img = bpy.data.images.load(filepath)
        width, height = img.size

        if max(width, height) > max_size:
            scale = max_size / max(width, height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img.scale(new_width, new_height)
            img.file_format = fmt.upper()
            img.save()
            width, height = new_width, new_height

        bpy.data.images.remove(img)

        return {"success": True, "width": width, "height": height, "filepath": filepath}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Command handlers - PolyHaven (full PBR from official)
# ---------------------------------------------------------------------------

def handle_get_polyhaven_categories(params: Dict) -> Any:
    asset_type = params.get("asset_type", "textures")
    if asset_type not in ("hdris", "textures", "models", "all"):
        return {"error": f"Invalid asset type: {asset_type}"}
    url = f"https://api.polyhaven.com/categories/{asset_type}"
    return _http_get_json(url)


def handle_search_polyhaven_assets(params: Dict) -> Any:
    asset_type = params.get("asset_type", "textures")
    categories = params.get("categories")
    url = f"https://api.polyhaven.com/assets?type={asset_type}"
    if categories:
        cats = categories if isinstance(categories, str) else ",".join(categories)
        url += f"&categories={cats}"
    data = _http_get_json(url, timeout=30)
    return {"total": len(data), "assets": list(data.keys())[:50]}


def handle_download_polyhaven_asset(params: Dict) -> Any:
    asset_id = params.get("asset_id", "")
    asset_type = params.get("asset_type", "textures")
    resolution = params.get("resolution", "1k")
    file_format = params.get("file_format", "jpg")
    files_data = params.get("files_data")

    if not files_data:
        url = f"https://api.polyhaven.com/files/{asset_id}"
        files_data = _http_get_json(url, timeout=30)

    try:
        if asset_type == "hdris":
            download_info = files_data["hdri"][resolution][file_format]
        elif asset_type == "textures":
            download_info = files_data.get("Diffuse", files_data.get("Color", {}))
            download_info = download_info.get(resolution, {}).get(file_format, {})
        else:
            download_info = files_data.get("blend", files_data.get("gltf", {}))
            download_info = download_info.get(resolution, {})
            download_info = next(iter(download_info.values()), {}) if download_info else {}
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Could not resolve download URL for '{asset_id}' ({resolution} {file_format}): {exc}")

    download_url = download_info.get("url") if isinstance(download_info, dict) else None
    if not download_url:
        raise ValueError(f"No download URL found for asset '{asset_id}' at {resolution}/{file_format}.")

    tmp_dir = bpy.app.tempdir
    dest = os.path.join(tmp_dir, f"{asset_id}_{resolution}.{file_format}")
    _http_download(download_url, dest)

    if asset_type == "hdris":
        world = bpy.context.scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world
        world.use_nodes = True
        node_tree = world.node_tree

        for node in node_tree.nodes:
            node_tree.nodes.remove(node)

        tex_coord = node_tree.nodes.new(type='ShaderNodeTexCoord')
        tex_coord.location = (-800, 0)

        mapping = node_tree.nodes.new(type='ShaderNodeMapping')
        mapping.location = (-600, 0)

        env_tex = node_tree.nodes.new(type='ShaderNodeTexEnvironment')
        env_tex.location = (-400, 0)
        env_tex.image = bpy.data.images.load(dest)

        if file_format.lower() == 'exr':
            try:
                env_tex.image.colorspace_settings.name = 'Linear'
            except Exception:
                env_tex.image.colorspace_settings.name = 'Non-Color'
        else:
            for color_space in ['Linear', 'Linear Rec.709', 'Non-Color']:
                try:
                    env_tex.image.colorspace_settings.name = color_space
                    break
                except Exception:
                    continue

        background = node_tree.nodes.new(type='ShaderNodeBackground')
        background.location = (-200, 0)

        output = node_tree.nodes.new(type='ShaderNodeOutputWorld')
        output.location = (0, 0)

        node_tree.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
        node_tree.links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
        node_tree.links.new(env_tex.outputs['Color'], background.inputs['Color'])
        node_tree.links.new(background.outputs['Background'], output.inputs['Surface'])

        bpy.context.scene.world = world
        return {"hdri_applied": asset_id, "file": dest, "world": world.name}
    else:
        return {"downloaded": asset_id, "file": dest, "note": "Use blender_set_texture to apply this texture."}


def handle_set_texture(params: Dict) -> Any:
    """Apply a previously downloaded PolyHaven texture to an object with full PBR node graph."""
    object_name = params.get("object_name", "")
    texture_id = params.get("texture_id", "")

    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}
    if not hasattr(obj, 'data') or not hasattr(obj.data, 'materials'):
        return {"error": f"Object {object_name} cannot accept materials"}

    # Find all images related to this texture
    texture_images = {}
    for img in bpy.data.images:
        if img.name.startswith(texture_id + "_"):
            map_type = img.name.split('_')[-1].split('.')[0]
            img.reload()
            if map_type.lower() in ['color', 'diffuse', 'albedo']:
                try:
                    img.colorspace_settings.name = 'sRGB'
                except Exception:
                    pass
            else:
                try:
                    img.colorspace_settings.name = 'Non-Color'
                except Exception:
                    pass
            if not img.packed_file:
                img.pack()
            texture_images[map_type] = img

    if not texture_images:
        return {"error": f"No texture images found for: {texture_id}. Please download the texture first."}

    # Create new material
    new_mat_name = f"{texture_id}_material_{object_name}"
    existing_mat = bpy.data.materials.get(new_mat_name)
    if existing_mat:
        bpy.data.materials.remove(existing_mat)

    new_mat = bpy.data.materials.new(name=new_mat_name)
    new_mat.use_nodes = True
    nodes = new_mat.node_tree.nodes
    links = new_mat.node_tree.links
    nodes.clear()

    # Create nodes
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (600, 0)

    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (300, 0)
    links.new(principled.outputs[0], output.inputs[0])

    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)

    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (-600, 0)
    mapping.vector_type = 'TEXTURE'
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    x_pos = -400
    y_pos = 300

    # First pass: create texture image nodes
    texture_nodes = {}
    for map_type, image in texture_images.items():
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.location = (x_pos, y_pos)
        tex_node.image = image

        if map_type.lower() in ['color', 'diffuse', 'albedo']:
            try:
                tex_node.image.colorspace_settings.name = 'sRGB'
            except Exception:
                pass
        else:
            try:
                tex_node.image.colorspace_settings.name = 'Non-Color'
            except Exception:
                pass

        links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])
        texture_nodes[map_type] = tex_node
        y_pos -= 250

    # Second pass: connect to Principled BSDF
    # Base Color
    for map_name in ['color', 'diffuse', 'albedo']:
        if map_name in texture_nodes:
            links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Base Color'])
            break

    # Roughness
    for map_name in ['roughness', 'rough']:
        if map_name in texture_nodes:
            links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Roughness'])
            break

    # Metallic
    for map_name in ['metallic', 'metalness', 'metal']:
        if map_name in texture_nodes:
            links.new(texture_nodes[map_name].outputs['Color'], principled.inputs['Metallic'])
            break

    # Normal
    for map_name in ['gl', 'dx', 'nor', 'normal']:
        if map_name in texture_nodes:
            normal_map_node = nodes.new(type='ShaderNodeNormalMap')
            normal_map_node.location = (100, 100)
            links.new(texture_nodes[map_name].outputs['Color'], normal_map_node.inputs['Color'])
            links.new(normal_map_node.outputs['Normal'], principled.inputs['Normal'])
            break

    # Displacement
    for map_name in ['displacement', 'disp', 'height']:
        if map_name in texture_nodes:
            disp_node = nodes.new(type='ShaderNodeDisplacement')
            disp_node.location = (300, -200)
            disp_node.inputs['Scale'].default_value = 0.1
            links.new(texture_nodes[map_name].outputs['Color'], disp_node.inputs['Height'])
            links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
            break

    # ARM (Ambient Occlusion, Roughness, Metallic)
    if 'arm' in texture_nodes:
        separate_rgb = nodes.new(type='ShaderNodeSeparateRGB')
        separate_rgb.location = (-200, -100)
        links.new(texture_nodes['arm'].outputs['Color'], separate_rgb.inputs['Image'])

        if not any(m in texture_nodes for m in ['roughness', 'rough']):
            links.new(separate_rgb.outputs['G'], principled.inputs['Roughness'])
        if not any(m in texture_nodes for m in ['metallic', 'metalness', 'metal']):
            links.new(separate_rgb.outputs['B'], principled.inputs['Metallic'])

        base_color_node = None
        for m in ['color', 'diffuse', 'albedo']:
            if m in texture_nodes:
                base_color_node = texture_nodes[m]
                break
        if base_color_node:
            mix_node = nodes.new(type='ShaderNodeMixRGB')
            mix_node.location = (100, 200)
            mix_node.blend_type = 'MULTIPLY'
            mix_node.inputs['Fac'].default_value = 0.8
            for link in base_color_node.outputs['Color'].links:
                if link.to_socket == principled.inputs['Base Color']:
                    links.remove(link)
            links.new(base_color_node.outputs['Color'], mix_node.inputs[1])
            links.new(separate_rgb.outputs['R'], mix_node.inputs[2])
            links.new(mix_node.outputs['Color'], principled.inputs['Base Color'])

    # AO (separate)
    if 'ao' in texture_nodes:
        base_color_node = None
        for m in ['color', 'diffuse', 'albedo']:
            if m in texture_nodes:
                base_color_node = texture_nodes[m]
                break
        if base_color_node:
            mix_node = nodes.new(type='ShaderNodeMixRGB')
            mix_node.location = (100, 200)
            mix_node.blend_type = 'MULTIPLY'
            mix_node.inputs['Fac'].default_value = 0.8
            for link in base_color_node.outputs['Color'].links:
                if link.to_socket == principled.inputs['Base Color']:
                    links.remove(link)
            links.new(base_color_node.outputs['Color'], mix_node.inputs[1])
            links.new(texture_nodes['ao'].outputs['Color'], mix_node.inputs[2])
            links.new(mix_node.outputs['Color'], principled.inputs['Base Color'])

    # Clear existing materials and assign
    while len(obj.data.materials) > 0:
        obj.data.materials.pop(index=0)
    obj.data.materials.append(new_mat)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.context.view_layer.update()

    return {
        "success": True,
        "message": f"Applied texture {texture_id} to {object_name}",
        "material": new_mat.name,
        "maps": list(texture_images.keys()),
    }


# ---------------------------------------------------------------------------
# Command handlers - PolyHaven Model Import (from official)
# ---------------------------------------------------------------------------

def handle_download_polyhaven_model(params: Dict) -> Any:
    """Download and import a 3D model from PolyHaven."""
    asset_id = params.get("asset_id", "")
    resolution = params.get("resolution", "1k")
    file_format = params.get("file_format", "gltf")

    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required for model downloads. Install with: pip install requests"}

    files_response = _requests.get(
        f"https://api.polyhaven.com/files/{asset_id}",
        headers=_REQ_HEADERS,
        timeout=30,
    )
    if files_response.status_code != 200:
        return {"error": f"Failed to get asset files: {files_response.status_code}"}

    files_data = files_response.json()

    if file_format not in files_data:
        file_format = next(iter(files_data.keys()), None)
        if not file_format:
            return {"error": "No model formats available"}

    if resolution not in files_data[file_format]:
        return {"error": f"Resolution {resolution} not available"}

    resolution_data = files_data[file_format][resolution]
    file_info = next(iter(resolution_data.values()), None)
    if not file_info or "url" not in file_info:
        return {"error": "Could not find download URL"}

    try:
        temp_dir = tempfile.mkdtemp()
        main_file_path = os.path.join(temp_dir, file_info["url"].split("/")[-1])
        response = _requests.get(file_info["url"], headers=_REQ_HEADERS, timeout=60)
        if response.status_code != 200:
            return {"error": f"Download failed: {response.status_code}"}

        with open(main_file_path, "wb") as f:
            f.write(response.content)

        # Download included files
        if "include" in file_info and file_info["include"]:
            for include_path, include_info in file_info["include"].items():
                include_url = include_info["url"]
                include_file_path = os.path.join(temp_dir, include_path)
                os.makedirs(os.path.dirname(include_file_path), exist_ok=True)
                include_resp = _requests.get(include_url, headers=_REQ_HEADERS, timeout=30)
                if include_resp.status_code == 200:
                    with open(include_file_path, "wb") as f:
                        f.write(include_resp.content)

        # Import
        if file_format in ("gltf", "glb"):
            bpy.ops.import_scene.gltf(filepath=main_file_path)
        elif file_format == "fbx":
            bpy.ops.import_scene.fbx(filepath=main_file_path)
        elif file_format == "obj":
            bpy.ops.import_scene.obj(filepath=main_file_path)
        elif file_format == "blend":
            with bpy.data.libraries.load(main_file_path, link=False) as (data_from, data_to):
                data_to.objects = data_from.objects
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
        else:
            return {"error": f"Unsupported format: {file_format}"}

        imported = [obj.name for obj in bpy.context.selected_objects]
        return {"success": True, "imported_objects": imported}
    except Exception as e:
        return {"error": f"Failed to import model: {str(e)}"}
    finally:
        with suppress(Exception):
            shutil.rmtree(temp_dir)


# ---------------------------------------------------------------------------
# Command handlers - Sketchfab (from official)
# ---------------------------------------------------------------------------

def _get_sketchfab_api_key():
    return bpy.context.scene.supermcp_sketchfab_api_key


def handle_get_sketchfab_status(params: Dict) -> Any:
    api_key = _get_sketchfab_api_key()
    enabled = bpy.context.scene.supermcp_use_sketchfab

    if api_key and _HAS_REQUESTS:
        try:
            resp = _requests.get(
                "https://api.sketchfab.com/v3/me",
                headers={"Authorization": f"Token {api_key}"},
                timeout=30,
            )
            if resp.status_code == 200:
                username = resp.json().get("username", "Unknown")
                return {"enabled": True, "message": f"Sketchfab ready. Logged in as: {username}"}
            else:
                return {"enabled": False, "message": f"Invalid API key (status {resp.status_code})"}
        except Exception as e:
            return {"enabled": False, "message": f"Error: {str(e)}"}

    if enabled and not api_key:
        return {"enabled": False, "message": "Sketchfab enabled but API key not set. Enter key in the Super MCP panel."}
    return {"enabled": False, "message": "Sketchfab is disabled. Enable in the Super MCP panel."}


def handle_search_sketchfab_models(params: Dict) -> Any:
    api_key = _get_sketchfab_api_key()
    if not api_key:
        return {"error": "Sketchfab API key not configured"}
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    query = params.get("query", "")
    categories = params.get("categories")
    count = params.get("count", 20)
    downloadable = params.get("downloadable", True)

    api_params = {
        "type": "models",
        "q": query,
        "count": count,
        "downloadable": downloadable,
        "archives_flavours": False,
    }
    if categories:
        api_params["categories"] = categories

    try:
        resp = _requests.get(
            "https://api.sketchfab.com/v3/search",
            headers={"Authorization": f"Token {api_key}"},
            params=api_params,
            timeout=30,
        )
        if resp.status_code == 401:
            return {"error": "Authentication failed. Check API key."}
        if resp.status_code != 200:
            return {"error": f"API error: {resp.status_code}"}
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def handle_get_sketchfab_model_preview(params: Dict) -> Any:
    api_key = _get_sketchfab_api_key()
    if not api_key:
        return {"error": "Sketchfab API key not configured"}
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    uid = params.get("uid", "")
    try:
        resp = _requests.get(
            f"https://api.sketchfab.com/v3/models/{uid}",
            headers={"Authorization": f"Token {api_key}"},
            timeout=30,
        )
        if resp.status_code != 200:
            return {"error": f"Failed to get model info: {resp.status_code}"}

        data = resp.json()
        thumbnails = data.get("thumbnails", {}).get("images", [])
        if not thumbnails:
            return {"error": "No thumbnails available"}

        selected = None
        for thumb in thumbnails:
            w = thumb.get("width", 0)
            if 400 <= w <= 800:
                selected = thumb
                break
        if not selected:
            selected = thumbnails[0]

        thumb_url = selected.get("url")
        img_resp = _requests.get(thumb_url, timeout=30)
        if img_resp.status_code != 200:
            return {"error": f"Thumbnail download failed: {img_resp.status_code}"}

        image_data = base64.b64encode(img_resp.content).decode('ascii')
        content_type = img_resp.headers.get("Content-Type", "")
        img_format = "png" if "png" in content_type else "jpeg"

        return {
            "success": True,
            "image_data": image_data,
            "format": img_format,
            "model_name": data.get("name", "Unknown"),
            "author": data.get("user", {}).get("username", "Unknown"),
            "uid": uid,
            "thumbnail_width": selected.get("width"),
            "thumbnail_height": selected.get("height"),
        }
    except Exception as e:
        return {"error": f"Failed to get preview: {str(e)}"}


def handle_download_sketchfab_model(params: Dict) -> Any:
    api_key = _get_sketchfab_api_key()
    if not api_key:
        return {"error": "Sketchfab API key not configured"}
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    uid = params.get("uid", "")
    normalize_size = params.get("normalize_size", False)
    target_size = params.get("target_size", 1.0)

    try:
        headers = {"Authorization": f"Token {api_key}"}
        resp = _requests.get(
            f"https://api.sketchfab.com/v3/models/{uid}/download",
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 401:
            return {"error": "Authentication failed"}
        if resp.status_code != 200:
            return {"error": f"Download request failed: {resp.status_code}"}

        data = resp.json()
        if data is None:
            return {"error": "Empty response"}

        gltf_data = data.get("gltf")
        if not gltf_data or not gltf_data.get("url"):
            return {"error": "No download URL available"}

        model_resp = _requests.get(gltf_data["url"], timeout=60)
        if model_resp.status_code != 200:
            return {"error": f"Download failed: {model_resp.status_code}"}

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f"{uid}.zip")
        with open(zip_path, "wb") as f:
            f.write(model_resp.content)

        # Extract with zip-slip protection
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                file_path = file_info.filename
                target_path = os.path.join(temp_dir, os.path.normpath(file_path))
                abs_temp = os.path.abspath(temp_dir)
                abs_target = os.path.abspath(target_path)
                if not abs_target.startswith(abs_temp):
                    with suppress(Exception):
                        shutil.rmtree(temp_dir)
                    return {"error": "Security: zip contains path traversal"}
                if ".." in file_path:
                    with suppress(Exception):
                        shutil.rmtree(temp_dir)
                    return {"error": "Security: zip contains directory traversal"}
            zip_ref.extractall(temp_dir)

        gltf_files = [f for f in os.listdir(temp_dir) if f.endswith('.gltf') or f.endswith('.glb')]
        if not gltf_files:
            with suppress(Exception):
                shutil.rmtree(temp_dir)
            return {"error": "No glTF file in archive"}

        main_file = os.path.join(temp_dir, gltf_files[0])
        bpy.ops.import_scene.gltf(filepath=main_file)

        imported = list(bpy.context.selected_objects)
        imported_names = [obj.name for obj in imported]

        # Normalize size if requested
        scale_applied = 1.0
        root_objects = [obj for obj in imported if obj.parent is None]

        def get_all_mesh_children(o):
            meshes = []
            if o.type == 'MESH':
                meshes.append(o)
            for child in o.children:
                meshes.extend(get_all_mesh_children(child))
            return meshes

        all_meshes = []
        for root in root_objects:
            all_meshes.extend(get_all_mesh_children(root))

        if all_meshes and normalize_size:
            all_min = mathutils.Vector((float('inf'), float('inf'), float('inf')))
            all_max = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))
            for mesh_obj in all_meshes:
                for corner in mesh_obj.bound_box:
                    wc = mesh_obj.matrix_world @ mathutils.Vector(corner)
                    all_min.x = min(all_min.x, wc.x)
                    all_min.y = min(all_min.y, wc.y)
                    all_min.z = min(all_min.z, wc.z)
                    all_max.x = max(all_max.x, wc.x)
                    all_max.y = max(all_max.y, wc.y)
                    all_max.z = max(all_max.z, wc.z)

            max_dim = max(all_max.x - all_min.x, all_max.y - all_min.y, all_max.z - all_min.z)
            if max_dim > 0:
                scale_factor = target_size / max_dim
                scale_applied = scale_factor
                for root in root_objects:
                    root.scale = (root.scale.x * scale_factor, root.scale.y * scale_factor, root.scale.z * scale_factor)
                bpy.context.view_layer.update()

        with suppress(Exception):
            shutil.rmtree(temp_dir)

        result = {"success": True, "imported_objects": imported_names}
        if normalize_size:
            result["scale_applied"] = round(scale_applied, 6)
            result["normalized"] = True
        return result

    except Exception as e:
        return {"error": f"Failed to download model: {str(e)}"}


# ---------------------------------------------------------------------------
# Command handlers - Hyper3D Rodin (from official)
# ---------------------------------------------------------------------------

def handle_get_hyper3d_status(params: Dict) -> Any:
    enabled = bpy.context.scene.supermcp_use_hyper3d
    if enabled:
        api_key = bpy.context.scene.supermcp_hyper3d_api_key
        if not api_key:
            return {"enabled": False, "message": "Hyper3D enabled but API key not set. Enter key in the Super MCP panel."}
        mode = bpy.context.scene.supermcp_hyper3d_mode
        key_type = "private" if api_key != RODIN_FREE_TRIAL_KEY else "free_trial"
        return {"enabled": True, "message": f"Hyper3D ready. Mode: {mode}, Key: {key_type}"}
    return {"enabled": False, "message": "Hyper3D is disabled. Enable in the Super MCP panel."}


def handle_create_rodin_job(params: Dict) -> Any:
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    mode = bpy.context.scene.supermcp_hyper3d_mode
    api_key = bpy.context.scene.supermcp_hyper3d_api_key

    text_prompt = params.get("text_prompt")
    images = params.get("images")  # list of (suffix, base64_data)
    bbox_condition = params.get("bbox_condition")

    if mode == "MAIN_SITE":
        files = []
        if images:
            for i, (img_suffix, img) in enumerate(images):
                files.append(("images", (f"{i:04d}{img_suffix}", img)))
        files.append(("tier", (None, "Sketch")))
        files.append(("mesh_mode", (None, "Raw")))
        if text_prompt:
            files.append(("prompt", (None, text_prompt)))
        if bbox_condition:
            files.append(("bbox_condition", (None, json.dumps(bbox_condition))))

        resp = _requests.post(
            "https://hyperhuman.deemos.com/api/v2/rodin",
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
        )
        return resp.json()

    elif mode == "FAL_AI":
        req_data = {"tier": "Sketch"}
        if images:
            req_data["input_image_urls"] = images
        if text_prompt:
            req_data["prompt"] = text_prompt
        if bbox_condition:
            req_data["bbox_condition"] = bbox_condition
        resp = _requests.post(
            "https://queue.fal.run/fal-ai/hyper3d/rodin",
            headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
            json=req_data,
        )
        return resp.json()

    return {"error": f"Unknown Hyper3D mode: {mode}"}


def handle_poll_rodin_job_status(params: Dict) -> Any:
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    mode = bpy.context.scene.supermcp_hyper3d_mode
    api_key = bpy.context.scene.supermcp_hyper3d_api_key

    if mode == "MAIN_SITE":
        subscription_key = params.get("subscription_key", "")
        resp = _requests.post(
            "https://hyperhuman.deemos.com/api/v2/status",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"subscription_key": subscription_key},
        )
        data = resp.json()
        return {"status_list": [i["status"] for i in data.get("jobs", [])]}

    elif mode == "FAL_AI":
        request_id = params.get("request_id", "")
        resp = _requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}/status",
            headers={"Authorization": f"KEY {api_key}"},
        )
        return resp.json()

    return {"error": f"Unknown mode: {mode}"}


def _clean_imported_glb(filepath, mesh_name=None):
    """Import GLB and clean up the hierarchy (from official)."""
    existing_objects = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=filepath)
    bpy.context.view_layer.update()

    imported_objects = list(set(bpy.data.objects) - existing_objects)
    if not imported_objects:
        return None

    mesh_obj = None
    if len(imported_objects) == 1 and imported_objects[0].type == 'MESH':
        mesh_obj = imported_objects[0]
    elif len(imported_objects) == 2:
        empty_objs = [i for i in imported_objects if i.type == "EMPTY"]
        if len(empty_objs) == 1:
            parent_obj = empty_objs[0]
            if len(parent_obj.children) == 1 and parent_obj.children[0].type == 'MESH':
                mesh_obj = parent_obj.children[0]
                mesh_obj.parent = None
                bpy.data.objects.remove(parent_obj)

    if mesh_obj and mesh_name:
        try:
            mesh_obj.name = mesh_name
            if mesh_obj.data:
                mesh_obj.data.name = mesh_name
        except Exception:
            pass

    return mesh_obj


def handle_import_generated_asset(params: Dict) -> Any:
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    mode = bpy.context.scene.supermcp_hyper3d_mode
    api_key = bpy.context.scene.supermcp_hyper3d_api_key
    name = params.get("name", "")

    if mode == "MAIN_SITE":
        task_uuid = params.get("task_uuid", "")
        resp = _requests.post(
            "https://hyperhuman.deemos.com/api/v2/download",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"task_uuid": task_uuid},
        )
        data = resp.json()
        temp_file = None
        for item in data.get("list", []):
            if item["name"].endswith(".glb"):
                temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=task_uuid, suffix=".glb")
                try:
                    dl_resp = _requests.get(item["url"], stream=True, timeout=60)
                    dl_resp.raise_for_status()
                    for chunk in dl_resp.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_file.close()
                except Exception as e:
                    temp_file.close()
                    os.unlink(temp_file.name)
                    return {"succeed": False, "error": str(e)}
                break
        else:
            return {"succeed": False, "error": "No GLB file found in generation result"}

        try:
            obj = _clean_imported_glb(temp_file.name, name)
            if not obj:
                return {"succeed": False, "error": "Failed to import GLB"}
            result = {
                "succeed": True,
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale),
            }
            if obj.type == "MESH":
                result["world_bounding_box"] = _get_aabb(obj)
            return result
        except Exception as e:
            return {"succeed": False, "error": str(e)}

    elif mode == "FAL_AI":
        request_id = params.get("request_id", "")
        resp = _requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}",
            headers={"Authorization": f"Key {api_key}"},
        )
        data = resp.json()
        temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=request_id, suffix=".glb")
        try:
            dl_resp = _requests.get(data["model_mesh"]["url"], stream=True, timeout=60)
            dl_resp.raise_for_status()
            for chunk in dl_resp.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()
        except Exception as e:
            temp_file.close()
            os.unlink(temp_file.name)
            return {"succeed": False, "error": str(e)}

        try:
            obj = _clean_imported_glb(temp_file.name, name)
            if not obj:
                return {"succeed": False, "error": "Failed to import GLB"}
            result = {
                "succeed": True,
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale),
            }
            if obj.type == "MESH":
                result["world_bounding_box"] = _get_aabb(obj)
            return result
        except Exception as e:
            return {"succeed": False, "error": str(e)}

    return {"error": f"Unknown mode: {mode}"}


# ---------------------------------------------------------------------------
# Command handlers - Hunyuan3D (from official)
# ---------------------------------------------------------------------------

def handle_get_hunyuan3d_status(params: Dict) -> Any:
    enabled = bpy.context.scene.supermcp_use_hunyuan3d
    mode = bpy.context.scene.supermcp_hunyuan3d_mode

    if not enabled:
        return {"enabled": False, "message": "Hunyuan3D is disabled. Enable in the Super MCP panel."}

    if mode == "OFFICIAL_API":
        sid = bpy.context.scene.supermcp_hunyuan3d_secret_id
        skey = bpy.context.scene.supermcp_hunyuan3d_secret_key
        if not sid or not skey:
            return {"enabled": False, "message": "Hunyuan3D enabled but SecretId/SecretKey not set."}
    elif mode == "LOCAL_API":
        url = bpy.context.scene.supermcp_hunyuan3d_api_url
        if not url:
            return {"enabled": False, "message": "Hunyuan3D enabled but API URL not set."}

    return {"enabled": True, "mode": mode, "message": "Hunyuan3D ready."}


def _get_tencent_cloud_sign_headers(method, path, head_params, data, service, region, secret_id, secret_key, host=None):
    """Generate TC3-HMAC-SHA256 signature headers for Tencent Cloud API."""
    timestamp = int(time.time())
    date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
    if not host:
        host = f"{service}.tencentcloudapi.com"

    payload_str = json.dumps(data)
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{head_params.get('Action', '').lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    canonical_request = f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_request}"

    def sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, service)
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": host,
        "X-TC-Action": head_params.get("Action", ""),
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": head_params.get("Version", ""),
        "X-TC-Region": region,
    }
    return headers, f"https://{host}"


def handle_generate_hunyuan3d_model(params: Dict) -> Any:
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    mode = bpy.context.scene.supermcp_hunyuan3d_mode
    text_prompt = params.get("text_prompt")
    image = params.get("image")

    if not text_prompt and not image:
        return {"error": "Prompt or image is required"}
    if text_prompt and image:
        return {"error": "Cannot provide both prompt and image"}

    if mode == "OFFICIAL_API":
        secret_id = bpy.context.scene.supermcp_hunyuan3d_secret_id
        secret_key = bpy.context.scene.supermcp_hunyuan3d_secret_key
        if not secret_id or not secret_key:
            return {"error": "SecretId or SecretKey not set"}

        if text_prompt and len(text_prompt) > 200:
            return {"error": "Prompt exceeds 200 characters"}

        data = {"Num": 1}
        if text_prompt:
            data["Prompt"] = text_prompt
        if image:
            if re.match(r'^https?://', image, re.IGNORECASE):
                data["ImageUrl"] = image
            else:
                try:
                    with open(image, "rb") as f:
                        data["ImageBase64"] = base64.b64encode(f.read()).decode("ascii")
                except Exception as e:
                    return {"error": f"Image encoding failed: {str(e)}"}

        head_params = {"Action": "SubmitHunyuanTo3DJob", "Version": "2023-09-01", "Region": "ap-guangzhou"}
        headers, endpoint = _get_tencent_cloud_sign_headers(
            "POST", "/", head_params, data, "hunyuan", "ap-guangzhou", secret_id, secret_key
        )
        resp = _requests.post(endpoint, headers=headers, data=json.dumps(data))
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"API error: {resp.status_code}"}

    elif mode == "LOCAL_API":
        base_url = bpy.context.scene.supermcp_hunyuan3d_api_url.rstrip('/')
        data = {
            "octree_resolution": bpy.context.scene.supermcp_hunyuan3d_octree_resolution,
            "num_inference_steps": bpy.context.scene.supermcp_hunyuan3d_num_inference_steps,
            "guidance_scale": bpy.context.scene.supermcp_hunyuan3d_guidance_scale,
            "texture": bpy.context.scene.supermcp_hunyuan3d_texture,
        }
        if text_prompt:
            data["text"] = text_prompt
        if image:
            if re.match(r'^https?://', image, re.IGNORECASE):
                try:
                    res = _requests.get(image, timeout=30)
                    res.raise_for_status()
                    data["image"] = base64.b64encode(res.content).decode("ascii")
                except Exception as e:
                    return {"error": f"Failed to download image: {str(e)}"}
            else:
                try:
                    with open(image, "rb") as f:
                        data["image"] = base64.b64encode(f.read()).decode("ascii")
                except Exception as e:
                    return {"error": f"Image encoding failed: {str(e)}"}

        resp = _requests.post(f"{base_url}/generate", json=data, timeout=120)
        if resp.status_code != 200:
            return {"error": f"Generation failed: {resp.text}"}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp:
            tmp.write(resp.content)
            tmp_name = tmp.name

        def import_handler():
            bpy.ops.import_scene.gltf(filepath=tmp_name)
            os.unlink(tmp_name)
            return None

        bpy.app.timers.register(import_handler)
        return {"status": "DONE", "message": "Generation and import scheduled"}

    return {"error": f"Unknown mode: {mode}"}


def handle_poll_hunyuan_job_status(params: Dict) -> Any:
    if not _HAS_REQUESTS:
        return {"error": "The 'requests' library is required"}

    job_id = params.get("job_id", "")
    if not job_id:
        return {"error": "Job ID required"}

    secret_id = bpy.context.scene.supermcp_hunyuan3d_secret_id
    secret_key = bpy.context.scene.supermcp_hunyuan3d_secret_key
    if not secret_id or not secret_key:
        return {"error": "SecretId or SecretKey not set"}

    clean_job_id = job_id.removeprefix("job_")
    data = {"JobId": clean_job_id}
    head_params = {"Action": "QueryHunyuanTo3DJob", "Version": "2023-09-01", "Region": "ap-guangzhou"}
    headers, endpoint = _get_tencent_cloud_sign_headers(
        "POST", "/", head_params, data, "hunyuan", "ap-guangzhou", secret_id, secret_key
    )
    resp = _requests.post(endpoint, headers=headers, data=json.dumps(data))
    if resp.status_code == 200:
        return resp.json()
    return {"error": f"API error: {resp.status_code}"}


def handle_import_generated_asset_hunyuan(params: Dict) -> Any:
    zip_file_url = params.get("zip_file_url", "")
    name = params.get("name", "")

    if not zip_file_url:
        return {"error": "Zip file URL required"}
    if not re.match(r'^https?://', zip_file_url, re.IGNORECASE):
        return {"error": "Invalid URL format"}

    temp_dir = tempfile.mkdtemp(prefix="hunyuan_")
    zip_path = os.path.join(temp_dir, "model.zip")
    obj_path = os.path.join(temp_dir, "model.obj")

    try:
        _http_download(zip_file_url, zip_path, timeout=60)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        for f in os.listdir(temp_dir):
            if f.endswith(".obj"):
                obj_path = os.path.join(temp_dir, f)
                break

        if not os.path.exists(obj_path):
            return {"succeed": False, "error": "OBJ file not found after extraction"}

        if bpy.app.version >= (4, 0, 0):
            bpy.ops.wm.obj_import(filepath=obj_path)
        else:
            bpy.ops.import_scene.obj(filepath=obj_path)

        imported = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not imported:
            return {"succeed": False, "error": "No mesh objects imported"}

        obj = imported[0]
        if name:
            obj.name = name

        result = {
            "succeed": True,
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }
        if obj.type == "MESH":
            result["world_bounding_box"] = _get_aabb(obj)
        return result
    except Exception as e:
        return {"succeed": False, "error": str(e)}
    finally:
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(obj_path):
                os.remove(obj_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Command handlers - Ollama (passthrough to MCP server)
# ---------------------------------------------------------------------------

def handle_set_ollama_model(params: Dict) -> Any:
    return {"ollama_model": params.get("model_name", "")}


def handle_set_ollama_url(params: Dict) -> Any:
    return {"ollama_url": params.get("url", "")}


def handle_get_ollama_models(_params: Dict) -> Any:
    return {"note": "Use blender_get_ollama_models on the MCP server side."}


# ---------------------------------------------------------------------------
# Command router
# ---------------------------------------------------------------------------

HANDLERS = {
    # Core (P0)
    "get_scene_info":              handle_get_scene_info,
    "get_object_info":             handle_get_object_info,
    "create_object":               handle_create_object,
    "modify_object":               handle_modify_object,
    "delete_object":               handle_delete_object,
    "set_material":                handle_set_material,
    "render_image":                handle_render_image,
    "execute_code":                handle_execute_code,
    # Viewport (P1)
    "get_viewport_screenshot":     handle_get_viewport_screenshot,
    # PolyHaven (P1)
    "get_polyhaven_categories":    handle_get_polyhaven_categories,
    "search_polyhaven_assets":     handle_search_polyhaven_assets,
    "download_polyhaven_asset":    handle_download_polyhaven_asset,
    "set_texture":                 handle_set_texture,
    "download_polyhaven_model":    handle_download_polyhaven_model,
    # Sketchfab (P2)
    "get_sketchfab_status":        handle_get_sketchfab_status,
    "search_sketchfab_models":     handle_search_sketchfab_models,
    "get_sketchfab_model_preview": handle_get_sketchfab_model_preview,
    "download_sketchfab_model":    handle_download_sketchfab_model,
    # Hyper3D (P2)
    "get_hyper3d_status":          handle_get_hyper3d_status,
    "create_rodin_job":            handle_create_rodin_job,
    "poll_rodin_job_status":       handle_poll_rodin_job_status,
    "import_generated_asset":      handle_import_generated_asset,
    # Hunyuan3D (P2)
    "get_hunyuan3d_status":        handle_get_hunyuan3d_status,
    "generate_hunyuan3d_model":    handle_generate_hunyuan3d_model,
    "poll_hunyuan_job_status":     handle_poll_hunyuan_job_status,
    "import_generated_asset_hunyuan": handle_import_generated_asset_hunyuan,
    # Ollama (P2)
    "set_ollama_model":            handle_set_ollama_model,
    "set_ollama_url":              handle_set_ollama_url,
    "get_ollama_models":           handle_get_ollama_models,
}


def _dispatch(command_type: str, params: Dict) -> bytes:
    """Route a command to its handler and return encoded response bytes."""
    handler = HANDLERS.get(command_type)
    if handler is None:
        return _err(f"Unknown command '{command_type}'. Available: {list(HANDLERS)}")

    if command_type in ("execute_code", "render_image"):
        try:
            result = handler(params)
            return _ok(result)
        except Exception as exc:
            tb = traceback.format_exc()
            return _err(f"{type(exc).__name__}: {exc}\n{tb}")

    result_holder: Dict[str, Any] = {}
    done_event = threading.Event()
    _main_thread_cmd_queue.put((handler, params, result_holder, done_event))

    if not bpy.app.timers.is_registered(_main_thread_command_processor):
        bpy.app.timers.register(_main_thread_command_processor, first_interval=0.05)

    if not done_event.wait(timeout=120.0):
        return _err(f"Command '{command_type}' timed out on main thread")

    if "error" in result_holder:
        return _err(str(result_holder["error"]))

    return _ok(result_holder["result"])


# ---------------------------------------------------------------------------
# TCP server (community framework + official bpy.app.timers thread safety)
# ---------------------------------------------------------------------------

def _handle_client(conn: socket.socket, addr) -> None:
    """Handle a single client TCP connection (one command per connection)."""
    print(f"[Blender Super MCP] Client handler started for {addr}")
    sys.stdout.flush()
    conn.settimeout(SOCKET_TIMEOUT)

    try:
        buffer = b""
        max_size = RECV_BUFFER * 128
        while True:
            chunk = conn.recv(RECV_BUFFER)
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > max_size:
                raise ValueError(f"Request too large ({len(buffer)} bytes)")
            try:
                message = json.loads(buffer.decode("utf-8").strip())
                break
            except json.JSONDecodeError:
                continue

        if not buffer:
            return
        cmd_type = message.get("type", "")
        cmd_params = message.get("params", {})
        print(f"[Blender Super MCP] Command from {addr}: {cmd_type}")
        sys.stdout.flush()

        try:
            result_bytes = _dispatch(cmd_type, cmd_params)
            conn.sendall(result_bytes)
            print(f"[Blender Super MCP] Response sent for {cmd_type}")
        except Exception as exc:
            print(f"[Blender Super MCP] Command failed: {exc}")
            sys.stdout.flush()
            conn.sendall(_err(str(exc)))

        sys.stdout.flush()

    except json.JSONDecodeError as exc:
        print(f"[Blender Super MCP] Invalid JSON from {addr}: {exc}")
        conn.sendall(_err(f"Invalid JSON: {exc}"))
    except Exception as exc:
        print(f"[Blender Super MCP] Error from {addr}: {exc}")
        sys.stdout.flush()
        try:
            conn.sendall(_err(str(exc)))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[Blender Super MCP] Client handler stopped for {addr}")
        sys.stdout.flush()


def _server_loop(host: str, port: int) -> None:
    """Main TCP server loop running in a background thread."""
    global _server_socket, _server_running
    print(f"[Blender Super MCP] Server thread started on {host}:{port}")
    sys.stdout.flush()

    _remove_stop_file()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(1)
    sock.settimeout(1.0)
    _server_socket = sock
    print(f"[Blender Super MCP] Listening on {host}:{port}")
    sys.stdout.flush()

    while _server_running and not _check_stop_file():
        try:
            conn, addr = sock.accept()
            print(f"[Blender Super MCP] Client from {addr}")
            sys.stdout.flush()
            t = threading.Thread(target=_handle_client, args=(conn, addr), daemon=True)
            t.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[Blender Super MCP] Accept error: {e}")
            sys.stdout.flush()

    sock.close()
    _server_socket = None
    print("[Blender Super MCP] Server stopped.")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Blender operators
# ---------------------------------------------------------------------------

class SUPERMCP_OT_StartServer(bpy.types.Operator):
    """Start the Blender Super MCP TCP server"""
    bl_idname = "supermcp.start_server"
    bl_label = "Start MCP Server"
    bl_description = "Start the TCP server that accepts MCP commands"

    def execute(self, context: bpy.types.Context):
        global _server_thread, _server_running
        if _server_running:
            self.report({"WARNING"}, "MCP server is already running.")
            return {"CANCELLED"}

        scene = context.scene
        _server_running = True
        _server_thread = threading.Thread(
            target=_server_loop,
            args=(DEFAULT_HOST, scene.supermcp_port),
            daemon=True,
        )
        _server_thread.start()
        scene.supermcp_server_running = True
        print(f"[Blender Super MCP] Server thread alive: {_server_thread.is_alive()}")
        sys.stdout.flush()
        self.report({"INFO"}, f"MCP server started on {DEFAULT_HOST}:{scene.supermcp_port}")
        return {"FINISHED"}


class SUPERMCP_OT_StopServer(bpy.types.Operator):
    """Stop the Blender Super MCP TCP server"""
    bl_idname = "supermcp.stop_server"
    bl_label = "Stop MCP Server"
    bl_description = "Shut down the MCP TCP server"

    def execute(self, context: bpy.types.Context):
        global _server_running, _server_thread, _server_socket
        if not _server_running:
            # Already stopped, just update the UI state
            context.scene.supermcp_server_running = False
            return {"CANCELLED"}

        _server_running = False
        _create_stop_file()
        if _server_socket:
            try:
                _server_socket.close()
            except Exception:
                pass
        if _server_thread:
            _server_thread.join(timeout=3.0)
            _server_thread = None
        context.scene.supermcp_server_running = False
        self.report({"INFO"}, "MCP server stopped.")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# UI Panel
# ---------------------------------------------------------------------------

class SUPERMCP_PT_Panel(bpy.types.Panel):
    """Blender Super MCP sidebar panel"""
    bl_label = "Super MCP"
    bl_idname = "SUPERMCP_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Super MCP"

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        scene = context.scene

        # Server settings
        layout.label(text="Server Settings", icon="NETWORK_DRIVE")
        col = layout.column(align=True)
        col.prop(scene, "supermcp_port")

        layout.separator()

        # Use _server_running (actual state) instead of scene.supermcp_server_running (persisted state)
        if _server_running:
            layout.label(text="● Server Running", icon="CHECKMARK")
            layout.operator("supermcp.stop_server", icon="CANCEL", text="Stop Server")
            layout.label(text=f"Listening on {DEFAULT_HOST}:{scene.supermcp_port}")
        else:
            layout.label(text="○ Server Stopped", icon="X")
            layout.operator("supermcp.start_server", icon="PLAY", text="Start Server")

        # PolyHaven
        layout.separator()
        layout.prop(scene, "supermcp_use_polyhaven", text="Poly Haven")

        # Hyper3D
        layout.prop(scene, "supermcp_use_hyper3d", text="Hyper3D Rodin")
        if scene.supermcp_use_hyper3d:
            box = layout.box()
            box.prop(scene, "supermcp_hyper3d_mode", text="Mode")
            box.prop(scene, "supermcp_hyper3d_api_key", text="API Key")
            box.operator("supermcp.set_hyper3d_free_trial_key", text="Use Free Trial Key")

        # Sketchfab
        layout.prop(scene, "supermcp_use_sketchfab", text="Sketchfab")
        if scene.supermcp_use_sketchfab:
            box = layout.box()
            box.prop(scene, "supermcp_sketchfab_api_key", text="API Key")

        # Hunyuan3D
        layout.prop(scene, "supermcp_use_hunyuan3d", text="Hunyuan 3D")
        if scene.supermcp_use_hunyuan3d:
            box = layout.box()
            box.prop(scene, "supermcp_hunyuan3d_mode", text="Mode")
            if scene.supermcp_hunyuan3d_mode == 'OFFICIAL_API':
                box.prop(scene, "supermcp_hunyuan3d_secret_id", text="SecretId")
                box.prop(scene, "supermcp_hunyuan3d_secret_key", text="SecretKey")
            if scene.supermcp_hunyuan3d_mode == 'LOCAL_API':
                box.prop(scene, "supermcp_hunyuan3d_api_url", text="API URL")
                box.prop(scene, "supermcp_hunyuan3d_octree_resolution", text="Octree Resolution")
                box.prop(scene, "supermcp_hunyuan3d_num_inference_steps", text="Inference Steps")
                box.prop(scene, "supermcp_hunyuan3d_guidance_scale", text="Guidance Scale")
                box.prop(scene, "supermcp_hunyuan3d_texture", text="Generate Texture")

        # Info
        layout.separator()
        box = layout.box()
        box.scale_y = 0.7
        box.label(text="MCP Server: stdio or HTTP")
        box.label(text="Blender Add-on: TCP port 9876")
        box.label(text="Ollama: port 11434")


class SUPERMCP_OT_SetFreeTrialKey(bpy.types.Operator):
    """Set the free trial API key for Hyper3D Rodin"""
    bl_idname = "supermcp.set_hyper3d_free_trial_key"
    bl_label = "Set Free Trial Key"

    def execute(self, context):
        context.scene.supermcp_hyper3d_api_key = RODIN_FREE_TRIAL_KEY
        context.scene.supermcp_hyper3d_mode = 'MAIN_SITE'
        self.report({'INFO'}, "Free trial API key set!")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

CLASSES = [
    SUPERMCP_OT_StartServer,
    SUPERMCP_OT_StopServer,
    SUPERMCP_OT_SetFreeTrialKey,
    SUPERMCP_PT_Panel,
]


def register():
    # Clean up any stale stop file from previous unload
    _remove_stop_file()
    bpy.types.Scene.supermcp_port = bpy.props.IntProperty(
        name="Port",
        description="TCP port for the Blender Super MCP server",
        default=DEFAULT_PORT,
        min=1024,
        max=65535,
    )
    bpy.types.Scene.supermcp_server_running = bpy.props.BoolProperty(default=False)

    # PolyHaven
    bpy.types.Scene.supermcp_use_polyhaven = bpy.props.BoolProperty(
        name="Use Poly Haven", description="Enable Poly Haven asset integration", default=False
    )

    # Hyper3D
    bpy.types.Scene.supermcp_use_hyper3d = bpy.props.BoolProperty(
        name="Use Hyper3D Rodin", description="Enable Hyper3D Rodin 3D generation", default=False
    )
    bpy.types.Scene.supermcp_hyper3d_mode = bpy.props.EnumProperty(
        name="Hyper3D Mode",
        items=[("MAIN_SITE", "hyper3d.ai", "hyper3d.ai"), ("FAL_AI", "fal.ai", "fal.ai")],
        default="MAIN_SITE",
    )
    bpy.types.Scene.supermcp_hyper3d_api_key = bpy.props.StringProperty(
        name="Hyper3D API Key", subtype="PASSWORD", default=""
    )

    # Sketchfab
    bpy.types.Scene.supermcp_use_sketchfab = bpy.props.BoolProperty(
        name="Use Sketchfab", description="Enable Sketchfab asset integration", default=False
    )
    bpy.types.Scene.supermcp_sketchfab_api_key = bpy.props.StringProperty(
        name="Sketchfab API Key", subtype="PASSWORD", default=""
    )

    # Hunyuan3D
    bpy.types.Scene.supermcp_use_hunyuan3d = bpy.props.BoolProperty(
        name="Use Hunyuan 3D", description="Enable Hunyuan 3D generation", default=False
    )
    bpy.types.Scene.supermcp_hunyuan3d_mode = bpy.props.EnumProperty(
        name="Hunyuan3D Mode",
        items=[("LOCAL_API", "Local API", "Local API"), ("OFFICIAL_API", "Official API", "Official API")],
        default="LOCAL_API",
    )
    bpy.types.Scene.supermcp_hunyuan3d_secret_id = bpy.props.StringProperty(
        name="SecretId", default=""
    )
    bpy.types.Scene.supermcp_hunyuan3d_secret_key = bpy.props.StringProperty(
        name="SecretKey", subtype="PASSWORD", default=""
    )
    bpy.types.Scene.supermcp_hunyuan3d_api_url = bpy.props.StringProperty(
        name="API URL", default="http://localhost:8081"
    )
    bpy.types.Scene.supermcp_hunyuan3d_octree_resolution = bpy.props.IntProperty(
        name="Octree Resolution", default=256, min=128, max=512
    )
    bpy.types.Scene.supermcp_hunyuan3d_num_inference_steps = bpy.props.IntProperty(
        name="Inference Steps", default=20, min=20, max=50
    )
    bpy.types.Scene.supermcp_hunyuan3d_guidance_scale = bpy.props.FloatProperty(
        name="Guidance Scale", default=5.5, min=1.0, max=10.0
    )
    bpy.types.Scene.supermcp_hunyuan3d_texture = bpy.props.BoolProperty(
        name="Generate Texture", default=False
    )

    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # Auto-start the TCP server for MCP connectivity
    global _server_thread, _server_running
    if not _server_running:
        _server_running = True
        _server_thread = threading.Thread(
            target=_server_loop,
            args=(DEFAULT_HOST, DEFAULT_PORT),
            daemon=True,
        )
        _server_thread.start()
        try:
            bpy.context.scene.supermcp_server_running = True
        except Exception:
            pass
        print(f"[Blender Super MCP] Server auto-started on {DEFAULT_HOST}:{DEFAULT_PORT}")
    print("[Blender Super MCP] Add-on registered. Open the N-sidebar in 3D View → Super MCP.")


def unregister():
    global _server_running, _server_socket
    _server_running = False

    # Signal any old server loops (from previous module load) to stop
    _create_stop_file()

    # Also try to close the socket directly
    if _server_socket:
        try:
            _server_socket.close()
        except Exception:
            pass
        _server_socket = None

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

    # Clean up scene properties
    props_to_delete = [
        "supermcp_port", "supermcp_server_running",
        "supermcp_use_polyhaven",
        "supermcp_use_hyper3d", "supermcp_hyper3d_mode", "supermcp_hyper3d_api_key",
        "supermcp_use_sketchfab", "supermcp_sketchfab_api_key",
        "supermcp_use_hunyuan3d", "supermcp_hunyuan3d_mode",
        "supermcp_hunyuan3d_secret_id", "supermcp_hunyuan3d_secret_key",
        "supermcp_hunyuan3d_api_url", "supermcp_hunyuan3d_octree_resolution",
        "supermcp_hunyuan3d_num_inference_steps", "supermcp_hunyuan3d_guidance_scale",
        "supermcp_hunyuan3d_texture",
    ]
    for prop in props_to_delete:
        try:
            delattr(bpy.types.Scene, prop)
        except Exception:
            pass

    print("[Blender Super MCP] Add-on unregistered.")


if __name__ == "__main__":
    register()
