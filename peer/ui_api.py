"""
Modern web UI API for the P2P file sharing system.
Provides dashboard, file upload, download, and peer management.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import asyncio
import os
import json
from pathlib import Path
from .identity import load_keys, get_peer_id
from .client import download_from_discovery, connect_to_peer
from .crypto import aes_encrypt
from .chunk_manager import get_file_metadata
from typing import Dict, List
import httpx

app = FastAPI(title="P2P File Sharing UI")

# Configuration
SHARED_DIR = "shared"
DOWNLOADS_DIR = "downloads"
DISCOVERY_URL = "http://localhost:8000"

# Global state for UI
ui_state = {
    "peer_id": None,
    "public_key": None,
    "port": 9000,
    "shared_files": [],
    "registered": False,
    "download_progress": {},
    "online_peers": []
}


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
    
    ui_state["peer_id"] = peer_id
    ui_state["public_key"] = public_key_pem.decode('utf-8')
    
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
        ui_state["shared_files"] = sorted(files, key=lambda x: x["name"])


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
            
            ui_state["online_peers"] = peers
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
        ui_state["port"] = port
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            files = [f["name"] for f in ui_state["shared_files"]]
            
            payload = {
                "peer_id": ui_state["peer_id"],
                "public_key": ui_state["public_key"],
                "port": port,
                "files": files
            }
            
            response = await client.post(f"{DISCOVERY_URL}/register", json=payload)
            ui_state["registered"] = True
            
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


# ============================================================================
# HTML DASHBOARD
# ============================================================================

def get_dashboard_html():
    """Return the modern dashboard HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>P2P File Sharing - Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            background: rgba(255, 255, 255, 0.95);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }

        h1 {
            font-size: 2em;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #f0f4ff;
            padding: 12px 20px;
            border-radius: 25px;
            font-weight: 500;
        }

        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #4CAF50;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .peer-id {
            font-family: monospace;
            font-size: 0.9em;
            color: #666;
        }

        main {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        @media (max-width: 1200px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: rgba(255, 255, 255, 0.98);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }

        .panel h2 {
            font-size: 1.3em;
            margin-bottom: 20px;
            color: #333;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel h2::before {
            display: inline-block;
            width: 4px;
            height: 24px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 2px;
        }

        /* Upload Area */
        .upload-area {
            border: 2px dashed #667eea;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: linear-gradient(135deg, #f5f7ff 0%, #fff 100%);
        }

        .upload-area:hover {
            border-color: #764ba2;
            background: linear-gradient(135deg, #f0f4ff 0%, #f9f7ff 100%);
        }

        .upload-area.dragover {
            border-color: #764ba2;
            background: #f0f4ff;
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 3em;
            margin-bottom: 10px;
        }

        .upload-text {
            color: #666;
            margin-bottom: 10px;
        }

        .upload-button {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 15px;
        }

        .upload-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }

        input[type="file"] {
            display: none;
        }

        /* File Lists */
        .file-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-height: 400px;
            overflow-y: auto;
        }

        .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: #f8f9ff;
            border-radius: 8px;
            transition: all 0.3s ease;
            border-left: 4px solid #667eea;
        }

        .file-item:hover {
            background: #f0f4ff;
            transform: translateX(5px);
        }

        .file-info {
            flex: 1;
        }

        .file-name {
            font-weight: 600;
            color: #333;
            margin-bottom: 4px;
        }

        .file-size {
            font-size: 0.85em;
            color: #999;
        }

        /* Buttons */
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 600;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(102, 126, 234, 0.3);
        }

        .btn-danger {
            background: #ff6b6b;
            color: white;
        }

        .btn-danger:hover {
            background: #ff5252;
        }

        .btn-secondary {
            background: #e9ecef;
            color: #333;
        }

        .btn-secondary:hover {
            background: #dee2e6;
        }

        /* Peers Section */
        .peers-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }

        .peer-card {
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            padding: 15px;
            border-radius: 10px;
            border: 1px solid rgba(102, 126, 234, 0.2);
            transition: all 0.3s;
        }

        .peer-card:hover {
            border-color: #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.15);
            transform: translateY(-3px);
        }

        .peer-title {
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }

        .peer-detail {
            font-size: 0.85em;
            color: #666;
            margin-bottom: 4px;
            font-family: monospace;
        }

        .peer-files {
            font-size: 0.85em;
            background: white;
            padding: 6px;
            border-radius: 4px;
            margin-top: 8px;
            color: #667eea;
            font-weight: 500;
        }

        /* Search */
        .search-section {
            margin-bottom: 20px;
        }

        .search-box {
            display: flex;
            gap: 10px;
        }

        .search-box input {
            flex: 1;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }

        .search-box input:focus {
            outline: none;
            border-color: #667eea;
        }

        /* Loading */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Empty States */
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #999;
        }

        .empty-icon {
            font-size: 3em;
            margin-bottom: 10px;
        }

        /* Notifications */
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 16px 24px;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            animation: slideIn 0.3s ease;
            z-index: 1000;
        }

        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        .notification.success {
            border-left: 4px solid #4CAF50;
        }

        .notification.error {
            border-left: 4px solid #ff6b6b;
        }

        .notification.info {
            border-left: 4px solid #667eea;
        }

        /* Progress Bar */
        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }

        .refresh-btn {
            padding: 10px 20px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }

        .refresh-btn:hover {
            transform: rotate(180deg);
            box-shadow: 0 8px 16px rgba(102, 126, 234, 0.3);
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }

        ::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 10px;
        }

        ::-webkit-scrollbar-thumb {
            background: #667eea;
            border-radius: 10px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #764ba2;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <div>
                    <h1>🌐 P2P File Sharing</h1>
                    <p class="peer-id" style="margin-top: 5px;">Peer ID: <span id="peer-id">Loading...</span></p>
                </div>
                <div class="status-badge">
                    <div class="status-dot"></div>
                    <span id="status-text">Online</span>
                </div>
            </div>
        </header>

        <main>
            <!-- Left Column -->
            <div>
                <!-- Upload Panel -->
                <div class="panel">
                    <h2>Share Files</h2>
                    <div class="upload-area" id="uploadArea">
                        <div class="upload-icon">📤</div>
                        <div class="upload-text">Drag files here or click to upload</div>
                        <button class="upload-button" onclick="document.getElementById('fileInput').click()">
                            Choose Files
                        </button>
                        <input type="file" id="fileInput" multiple>
                    </div>
                </div>

                <!-- Shared Files Panel -->
                <div class="panel" style="margin-top: 20px;">
                    <h2>Shared Files</h2>
                    <div id="sharedFiles" class="file-list">
                        <div class="empty-state">
                            <div class="empty-icon">📁</div>
                            <p>No files shared yet</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Column -->
            <div>
                <!-- Peers Panel -->
                <div class="panel">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0;">Online Peers</h2>
                        <button class="refresh-btn" onclick="refreshPeers()">🔄</button>
                    </div>
                    <div id="peersList" class="peers-list">
                        <div class="empty-state" style="grid-column: 1/-1;">
                            <div class="empty-icon">👥</div>
                            <p>No peers online</p>
                        </div>
                    </div>
                </div>

                <!-- Search & Download Panel -->
                <div class="panel" style="margin-top: 20px;">
                    <h2>Download Files</h2>
                    <div class="search-section">
                        <div class="search-box">
                            <input type="text" id="searchInput" placeholder="Search for files...">
                            <button class="btn btn-primary" onclick="searchFiles()">Search</button>
                        </div>
                    </div>
                    <div id="searchResults"></div>
                </div>
            </div>
        </main>

        <!-- Downloads Section -->
        <div class="panel">
            <h2>Downloaded Files</h2>
            <div id="downloadedFiles" class="file-list">
                <div class="empty-state">
                    <div class="empty-icon">📥</div>
                    <p>No files downloaded yet</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/api';

        // =====================================================================
        // INITIALIZATION
        // =====================================================================

        document.addEventListener('DOMContentLoaded', async () => {
            await loadStatus();
            await refreshSharedFiles();
            await refreshDownloadedFiles();
            await refreshPeers();

            setupUploadArea();
            setupSearch();

            // Refresh data periodically
            setInterval(refreshPeers, 10000);  // Every 10 seconds
            setInterval(refreshSharedFiles, 5000);  // Every 5 seconds
        });

        // =====================================================================
        // STATUS & INITIALIZATION
        // =====================================================================

        async function loadStatus() {
            try {
                const response = await fetch(`${API_BASE}/status`);
                const data = await response.json();

                document.getElementById('peer-id').textContent = data.peer_id;

                // Try to register with discovery
                try {
                    await fetch(`${API_BASE}/register`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ port: data.port })
                    });
                } catch (e) {
                    console.log('Discovery service not available');
                }
            } catch (error) {
                console.error('Error loading status:', error);
                showNotification('Failed to load status', 'error');
            }
        }

        // =====================================================================
        // FILE OPERATIONS
        // =====================================================================

        function setupUploadArea() {
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, preventDefaults, false);
            });

            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }

            ['dragenter', 'dragover'].forEach(eventName => {
                uploadArea.addEventListener(eventName, () => {
                    uploadArea.classList.add('dragover');
                });
            });

            ['dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, () => {
                    uploadArea.classList.remove('dragover');
                });
            });

            uploadArea.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                fileInput.files = files;
                handleFileSelect();
            });

            fileInput.addEventListener('change', handleFileSelect);
        }

        async function handleFileSelect() {
            const fileInput = document.getElementById('fileInput');
            const files = fileInput.files;

            for (let file of files) {
                await uploadFile(file);
            }

            fileInput.value = '';
            await refreshSharedFiles();
        }

        async function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch(`${API_BASE}/upload`, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    showNotification(`✓ Uploaded: ${data.filename}`, 'success');
                } else {
                    showNotification(`✗ Failed to upload: ${file.name}`, 'error');
                }
            } catch (error) {
                showNotification(`✗ Error uploading file: ${error.message}`, 'error');
            }
        }

        async function deleteSharedFile(filename) {
            if (!confirm(`Delete "${filename}" from shared files?`)) return;

            try {
                const response = await fetch(`${API_BASE}/shared/${filename}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    showNotification(`✓ Deleted: ${filename}`, 'success');
                    await refreshSharedFiles();
                }
            } catch (error) {
                showNotification(`✗ Error deleting file: ${error.message}`, 'error');
            }
        }

        async function deleteDownloadedFile(filename) {
            if (!confirm(`Delete "${filename}"?`)) return;

            try {
                const response = await fetch(`${API_BASE}/download/${filename}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    showNotification(`✓ Deleted: ${filename}`, 'success');
                    await refreshDownloadedFiles();
                }
            } catch (error) {
                showNotification(`✗ Error deleting file: ${error.message}`, 'error');
            }
        }

        async function refreshSharedFiles() {
            try {
                const response = await fetch(`${API_BASE}/status`);
                const data = await response.json();

                const container = document.getElementById('sharedFiles');

                if (data.shared_files.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-icon">📁</div>
                            <p>No files shared yet</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = data.shared_files.map(file => `
                    <div class="file-item">
                        <div class="file-info">
                            <div class="file-name">📄 ${escapeHtml(file.name)}</div>
                            <div class="file-size">${file.size_mb} MB</div>
                        </div>
                        <button class="btn btn-danger" onclick="deleteSharedFile('${escapeHtml(file.name)}')">Delete</button>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error refreshing shared files:', error);
            }
        }

        async function refreshDownloadedFiles() {
            try {
                const response = await fetch(`${API_BASE}/downloads`);
                const data = await response.json();

                const container = document.getElementById('downloadedFiles');

                if (data.downloads.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-icon">📥</div>
                            <p>No files downloaded yet</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = data.downloads.map(file => `
                    <div class="file-item">
                        <div class="file-info">
                            <div class="file-name">✓ ${escapeHtml(file.name)}</div>
                            <div class="file-size">${file.size_mb} MB</div>
                        </div>
                        <button class="btn btn-danger" onclick="deleteDownloadedFile('${escapeHtml(file.name)}')">Delete</button>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error refreshing downloads:', error);
            }
        }

        // =====================================================================
        // PEERS & SEARCH
        // =====================================================================

        async function refreshPeers() {
            try {
                const response = await fetch(`${API_BASE}/peers`);
                const data = await response.json();

                const container = document.getElementById('peersList');

                if (data.peers.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state" style="grid-column: 1/-1;">
                            <div class="empty-icon">👥</div>
                            <p>No peers online</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = data.peers.map(peer => `
                    <div class="peer-card">
                        <div class="peer-title">🔗 ${escapeHtml(peer.peer_id)}</div>
                        <div class="peer-detail">${escapeHtml(peer.ip)}:${peer.port}</div>
                        <div class="peer-files">${peer.files} file(s)</div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error refreshing peers:', error);
            }
        }

        function setupSearch() {
            const searchInput = document.getElementById('searchInput');
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    searchFiles();
                }
            });
        }

        async function searchFiles() {
            const filename = document.getElementById('searchInput').value.trim();
            if (!filename) {
                showNotification('Please enter a filename', 'info');
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/peers/search?filename=${encodeURIComponent(filename)}`);
                const data = await response.json();

                const container = document.getElementById('searchResults');

                if (data.error || data.found === 0) {
                    container.innerHTML = `
                        <div class="empty-state" style="margin-top: 20px;">
                            <div class="empty-icon">🔍</div>
                            <p>No peers found with this file</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = `
                    <div style="margin-top: 20px;">
                        <div style="font-weight: 600; margin-bottom: 12px; color: #333;">
                            Found on ${data.found} peer(s):
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                            ${data.peers.map(peer => `
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #f8f9ff; border-radius: 8px; border-left: 4px solid #667eea;">
                                    <div>
                                        <div style="font-weight: 600; color: #333;">${escapeHtml(peer.peer_id)}</div>
                                        <div style="font-size: 0.85em; color: #666; font-family: monospace; margin-top: 4px;">${escapeHtml(peer.ip)}:${peer.port}</div>
                                    </div>
                                    <button class="btn btn-primary" onclick="downloadFromPeer('${escapeHtml(filename)}', '${escapeHtml(peer.peer_id_full)}', '${escapeHtml(peer.ip)}', ${peer.port})">
                                        Download
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            } catch (error) {
                showNotification(`Error searching: ${error.message}`, 'error');
            }
        }

        async function downloadFromPeer(filename, peerId, ip, port) {
            try {
                const response = await fetch(`${API_BASE}/download`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: filename,
                        peer_id: peerId,
                        ip: ip,
                        port: port
                    })
                });

                if (response.ok) {
                    showNotification(`⏳ Downloading ${filename}...`, 'info');

                    // Poll progress
                    const checkProgress = async () => {
                        const progressResponse = await fetch(`${API_BASE}/download-progress/${encodeURIComponent(filename)}`);
                        const progress = await progressResponse.json();

                        if (progress.status === 'completed') {
                            showNotification(`✓ Download complete: ${filename}`, 'success');
                            await refreshDownloadedFiles();
                        } else if (progress.status === 'failed') {
                            showNotification(`✗ Download failed: ${progress.error || 'Unknown error'}`, 'error');
                        } else {
                            setTimeout(checkProgress, 500);
                        }
                    };

                    setTimeout(checkProgress, 500);
                }
            } catch (error) {
                showNotification(`Error starting download: ${error.message}`, 'error');
            }
        }

        // =====================================================================
        // UTILITIES
        // =====================================================================

        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.textContent = message;

            document.body.appendChild(notification);

            setTimeout(() => {
                notification.style.animation = 'slideIn 0.3s ease reverse';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
