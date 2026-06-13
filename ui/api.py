"""
FastAPI application for the P2P file sharing UI.
Provides REST endpoints for dashboard interaction.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path
from typing import Dict, List
import httpx
import sys
import asyncio
import io
import base64
import qrcode
from pyzbar.pyzbar import decode
from PIL import Image

# Add parent directory to path for peer imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from peer.identity import load_keys, get_peer_id
from peer.client import connect_to_peer
from peer.chunk_manager import get_file_metadata

from .config import SHARED_DIR, DOWNLOADS_DIR, DISCOVERY_URL
from .state import ui_state, update_state
from .templates import get_dashboard_html

app = FastAPI(title="P2P File Sharing UI")

# Mount static files (CSS, JS)
static_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


async def heartbeat_loop():
    """Send periodic heartbeats to keep peer registered with discovery service."""
    while True:
        try:
            await asyncio.sleep(30)  # Heartbeat every 30 seconds
            if not ui_state["peer_id"]:
                continue
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{DISCOVERY_URL}/heartbeat",
                    params={"peer_id": ui_state["peer_id"]}
                )
                print(f"[HEARTBEAT] Sent: {response.json()}")
        except Exception as e:
            print(f"[HEARTBEAT ERROR] {str(e)}")


async def auto_register():
    """Register with discovery service on startup."""
    try:
        await asyncio.sleep(1)  # Wait for startup to complete
        
        files = [f["name"] for f in ui_state["shared_files"]]
        peer_ip = get_local_ip()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "peer_id": ui_state["peer_id"],
                "public_key": ui_state["public_key"],
                "port": 9000,  # File transfer port
                "files": files,
                "ip": peer_ip
            }
            
            response = await client.post(f"{DISCOVERY_URL}/register", json=payload)
            update_state("registered", True)
            print(f"[AUTO-REGISTER] Registered with discovery at {peer_ip}:9000")
            print(f"[AUTO-REGISTER] Response: {response.json()}")
    except Exception as e:
        print(f"[AUTO-REGISTER ERROR] Failed to register with discovery: {str(e)}")


@app.on_event("startup")
async def startup():
    """Initialize peer identity on startup."""
    private_key, public_key = load_keys()
    peer_id = get_peer_id(public_key)
    
    from cryptography.hazmat.primitives import serialization
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    update_state("peer_id", peer_id)
    update_state("public_key", public_key_pem.decode('utf-8'))
    
    os.makedirs(SHARED_DIR, exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    
    refresh_shared_files()
    
    # Initialize connected peers list
    if "connected_peers" not in ui_state:
        ui_state["connected_peers"] = {}
    
    # Start automatic registration and heartbeat tasks
    asyncio.create_task(auto_register())
    asyncio.create_task(heartbeat_loop())


def refresh_shared_files():
    """Scan shared directory and update file list."""
    if os.path.exists(SHARED_DIR):
        files = []
        for f in os.listdir(SHARED_DIR):
            path = os.path.join(SHARED_DIR, f)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                files.append({"name": f, "size": size, "size_mb": round(size / 1024 / 1024, 2)})
        update_state("shared_files", sorted(files, key=lambda x: x["name"]))


async def refresh_online_peers():
    """Query discovery service for online peers."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DISCOVERY_URL}/peers")
            peers_data = response.json()
            
            peers = []
            for peer in peers_data.get("peers", []):
                files_count = len(peer.get("files", []))
                peers.append({
                    "peer_id": peer["peer_id"][:16] + "...",
                    "ip": peer["ip"],
                    "port": peer["port"],
                    "files": files_count,
                    "file_list": peer.get("files", [])
                })
            
            update_state("online_peers", peers)
    except Exception as e:
        print(f"Error refreshing peers: {e}")


# ============================================================================
# HTTP ENDPOINTS
# ============================================================================

@app.get("/")
async def serve_dashboard():
    """Serve the main UI dashboard."""
    return HTMLResponse(get_dashboard_html())


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return {
        "peer_id": ui_state["peer_id"][:16] + "...",
        "peer_id_full": ui_state["peer_id"],
        "port": ui_state["port"],
        "registered": ui_state["registered"],
        "shared_files": ui_state["shared_files"],
        "shared_files_count": len(ui_state["shared_files"]),
        "total_shared_size": sum(f["size"] for f in ui_state["shared_files"]),
    }


@app.get("/api/peers")
async def get_peers():
    """Get list of online peers."""
    await refresh_online_peers()
    return {"peers": ui_state["online_peers"]}


@app.get("/api/peers/search")
async def search_peers(filename: str):
    """Search peers for a specific file."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DISCOVERY_URL}/peers", params={"file": filename})
            peers_data = response.json()
            
            peers = []
            for peer in peers_data.get("peers", []):
                peers.append({
                    "peer_id": peer["peer_id"][:16] + "...",
                    "peer_id_full": peer["peer_id"],
                    "ip": peer["ip"],
                    "port": peer["port"]
                })
            
            return {
                "filename": filename,
                "found": len(peers),
                "peers": peers
            }
    except Exception as e:
        return {"error": str(e), "found": 0, "peers": []}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to the shared directory."""
    try:
        os.makedirs(SHARED_DIR, exist_ok=True)
        file_path = os.path.join(SHARED_DIR, file.filename)
        
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        refresh_shared_files()
        
        return {
            "status": "success",
            "filename": file.filename,
            "size": len(contents),
            "size_mb": round(len(contents) / 1024 / 1024, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download")
async def download_file(
    filename: str,
    peer_id: str,
    ip: str,
    port: int,
    background_tasks: BackgroundTasks
):
    """Download a file from a peer."""
    try:
        # Store progress tracker
        ui_state["download_progress"][filename] = {
            "status": "downloading",
            "progress": 0,
            "peer": f"{ip}:{port}"
        }
        
        async def download_bg():
            try:
                success = await connect_to_peer(ip, port, filename, DOWNLOADS_DIR)
                ui_state["download_progress"][filename] = {
                    "status": "completed" if success else "failed",
                    "progress": 100 if success else 0,
                    "peer": f"{ip}:{port}"
                }
            except Exception as e:
                ui_state["download_progress"][filename] = {
                    "status": "failed",
                    "error": str(e),
                    "peer": f"{ip}:{port}"
                }
        
        background_tasks.add_task(download_bg)
        
        return {
            "status": "downloading",
            "filename": filename,
            "peer": f"{ip}:{port}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/download-progress/{filename}")
async def get_download_progress(filename: str):
    """Get download progress for a file."""
    progress = ui_state["download_progress"].get(filename, {
        "status": "unknown",
        "progress": 0
    })
    return progress


@app.get("/api/downloads")
async def list_downloads():
    """List downloaded files."""
    files = []
    if os.path.exists(DOWNLOADS_DIR):
        for f in os.listdir(DOWNLOADS_DIR):
            path = os.path.join(DOWNLOADS_DIR, f)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                files.append({
                    "name": f,
                    "size": size,
                    "size_mb": round(size / 1024 / 1024, 2)
                })
    
    return {"downloads": sorted(files, key=lambda x: x["name"])}


def get_local_ip():
    """Get the local machine's actual IP address."""
    import socket
    try:
        # Connect to a dummy server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"  # Fallback


@app.post("/api/register")
async def register_peer(port: int, ip: str = None):
    """Register this peer with the discovery service."""
    try:
        update_state("port", port)
        
        # Use provided IP or detect actual network IP
        peer_ip = ip if ip else get_local_ip()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            files = [f["name"] for f in ui_state["shared_files"]]
            
            payload = {
                "peer_id": ui_state["peer_id"],
                "public_key": ui_state["public_key"],
                "port": port,
                "files": files,
                "ip": peer_ip  # Explicitly send IP address
            }
            
            response = await client.post(f"{DISCOVERY_URL}/register", json=payload)
            update_state("registered", True)
            
            print(f"[REGISTER] Registered with discovery as {peer_ip}:{port}")
            
            return {
                "status": "registered",
                "peer_id": ui_state["peer_id"][:16] + "...",
                "port": port,
                "ip": peer_ip
            }
    except Exception as e:
        print(f"[REGISTER ERROR] {str(e)}")
        return {"status": "error", "error": str(e)}


@app.delete("/api/shared/{filename}")
async def delete_shared_file(filename: str):
    """Delete a file from the shared directory."""
    try:
        file_path = os.path.join(SHARED_DIR, filename)
        
        # Security check
        if not os.path.abspath(file_path).startswith(os.path.abspath(SHARED_DIR)):
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        if os.path.exists(file_path):
            os.remove(file_path)
            refresh_shared_files()
            return {"status": "deleted", "filename": filename}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/download/{filename}")
async def delete_downloaded_file(filename: str):
    """Delete a downloaded file."""
    try:
        file_path = os.path.join(DOWNLOADS_DIR, filename)
        
        # Security check
        if not os.path.abspath(file_path).startswith(os.path.abspath(DOWNLOADS_DIR)):
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"status": "deleted", "filename": filename}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# QR CODE ENDPOINTS
# ============================================================================

@app.get("/api/qr/generate")
async def generate_qr(full_mode: bool = False):
    """Generate a QR code containing peer info.
    
    Args:
        full_mode: If True, include IP:port for direct connection.
                   If False, include peer_id only (discovery lookup).
    """
    try:
        peer_id = ui_state["peer_id"]
        if not peer_id:
            raise HTTPException(status_code=400, detail="Peer ID not initialized")
        
        ip = get_local_ip()
        
        if full_mode:
            # Full connection URL: http://ip:8080
            dashboard_url = f"http://{ip}:8080"
            qr_data = dashboard_url
            qr_label = dashboard_url
        else:
            # Peer ID only (discovery lookup)
            qr_data = peer_id
            qr_label = f"{peer_id[:16]}"
        
        # Create QR code
        qr = qrcode.QRCode(
            version=None,  # Auto-determine version
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            "status": "success",
            "peer_id": peer_id,
            "mode": "full_connection" if full_mode else "discovery_lookup",
            "qr_data": qr_data,
            "qr_label": qr_label,
            "dashboard_url": f"http://{ip}:8080" if full_mode else None,
            "qr_image": f"data:image/png;base64,{img_base64}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/qr/decode")
async def decode_qr(file: UploadFile = File(...)):
    """Decode a QR code image and extract peer connection info."""
    try:
        # Read uploaded file
        contents = await file.read()
        
        # Try to decode with pyzbar
        try:
            img = Image.open(io.BytesIO(contents))
            decoded_objects = decode(img)
            
            if not decoded_objects:
                raise HTTPException(status_code=400, detail="No QR code found in image")
            
            # Extract data from first QR code
            qr_data = decoded_objects[0].data.decode('utf-8')
            
            # Parse QR data - can be URL, peer_id, or "peer_id|ip|port"
            if qr_data.startswith('http://') or qr_data.startswith('https://'):
                # Dashboard URL
                return {
                    "status": "success",
                    "mode": "dashboard_url",
                    "url": qr_data,
                    "display_text": qr_data
                }
            elif '|' in qr_data:
                # Full connection string
                parts = qr_data.split('|')
                if len(parts) != 3:
                    raise HTTPException(status_code=400, detail="Invalid connection string format")
                
                peer_id, ip, port_str = parts
                try:
                    port = int(port_str)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid port number")
                
                # Validate peer ID format (64 hex characters)
                if len(peer_id) != 64 or not all(c in '0123456789abcdef' for c in peer_id):
                    raise HTTPException(status_code=400, detail="Invalid peer ID format")
                
                return {
                    "status": "success",
                    "mode": "direct_connect",
                    "peer_id": peer_id,
                    "ip": ip,
                    "port": port
                }
            else:
                # Peer ID only
                peer_id = qr_data
                
                # Validate peer ID format (64 hex characters)
                if len(peer_id) != 64 or not all(c in '0123456789abcdef' for c in peer_id):
                    raise HTTPException(status_code=400, detail="Invalid peer ID format")
                
                return {
                    "status": "success",
                    "mode": "discovery_lookup",
                    "peer_id": peer_id
                }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to decode QR: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/peers/lookup")
async def lookup_peer(peer_id: str):
    """Look up a specific peer by peer ID."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DISCOVERY_URL}/peers")
            peers_data = response.json()
            
            # Find matching peer
            for peer in peers_data.get("peers", []):
                if peer["peer_id"] == peer_id:
                    return {
                        "status": "found",
                        "peer": {
                            "peer_id": peer["peer_id"],
                            "peer_id_short": peer["peer_id"][:16] + "...",
                            "ip": peer["ip"],
                            "port": peer["port"],
                            "files": peer.get("files", []),
                            "files_count": len(peer.get("files", []))
                        }
                    }
            
            raise HTTPException(status_code=404, detail="Peer not found in discovery service")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/peers/connect")
async def connect_to_direct_peer(peer_id: str, ip: str, port: int):
    """Establish direct connection to a peer via IP:port.
    
    Bypasses discovery service for direct P2P pairing.
    """
    try:
        # Validate inputs
        if len(peer_id) != 64 or not all(c in '0123456789abcdef' for c in peer_id):
            raise HTTPException(status_code=400, detail="Invalid peer ID")
        
        # Try to establish connection to verify peer is reachable
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Simple connection test
                response = await client.get(f"http://{ip}:{port}")
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Cannot reach peer at {ip}:{port}")
        
        # Add to connected peers list
        connected_peer = {
            "peer_id": peer_id,
            "peer_id_short": peer_id[:16] + "...",
            "ip": ip,
            "port": port,
            "status": "connected"
        }
        
        # Store in state (using peer_id as key to avoid duplicates)
        if "connected_peers" not in ui_state:
            ui_state["connected_peers"] = {}
        
        ui_state["connected_peers"][peer_id] = connected_peer
        
        return {
            "status": "connected",
            "peer": connected_peer
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/peers/connected")
async def get_connected_peers():
    """Get list of directly connected peers."""
    connected = ui_state.get("connected_peers", {})
    return {
        "connected_peers": list(connected.values()),
        "count": len(connected)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
