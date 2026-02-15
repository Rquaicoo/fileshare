"""
FastAPI application for the P2P file sharing UI.
Provides REST endpoints for dashboard interaction.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
import os
from pathlib import Path
from typing import Dict, List
import httpx
import sys

# Add parent directory to path for peer imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from peer.identity import load_keys, get_peer_id
from peer.client import connect_to_peer
from peer.chunk_manager import get_file_metadata

from .config import SHARED_DIR, DOWNLOADS_DIR, DISCOVERY_URL
from .state import ui_state, update_state
from .templates import get_dashboard_html

app = FastAPI(title="P2P File Sharing UI")


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


@app.post("/api/register")
async def register_peer(port: int):
    """Register this peer with the discovery service."""
    try:
        update_state("port", port)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            files = [f["name"] for f in ui_state["shared_files"]]
            
            payload = {
                "peer_id": ui_state["peer_id"],
                "public_key": ui_state["public_key"],
                "port": port,
                "files": files
            }
            
            response = await client.post(f"{DISCOVERY_URL}/register", json=payload)
            update_state("registered", True)
            
            return {
                "status": "registered",
                "peer_id": ui_state["peer_id"][:16] + "...",
                "port": port
            }
    except Exception as e:
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
