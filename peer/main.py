from fastapi import FastAPI, Request, HTTPException
from .identity import load_keys, get_peer_id
from pydantic import BaseModel
from typing import List, Dict
import time

app = FastAPI()

PEERS: Dict[str, Dict] = {}
TIL = 60  # Time-to-live for peer entries in seconds

class RegisterRequest(BaseModel):
    peer_id: str
    public_key: str
    port: int
    files: List[str]
    ip: str = None  # Peer can optionally provide its own IP
    

@app.post("/register")
async def register_peer(request: Request, data: RegisterRequest):
    # Use provided IP, fallback to client IP detection
    client_ip = data.ip if data.ip else request.client.host
    
    # Map localhost to actual IP for multi-device scenarios
    if client_ip in ["127.0.0.1", "localhost"]:
        client_ip = request.client.host  # Still use request IP as fallback
    
    PEERS[data.peer_id] = {
        "ip": client_ip,
        "port": data.port,
        "public_key": data.public_key,
        "files": data.files,
        "last_seen": time.time()
    }
    
    print(f"[DISCOVERY] Registered peer {data.peer_id[:8]}... at {client_ip}:{data.port}")
    
    return {"message": "registered", "ip": client_ip}


@app.get("/heartbeat")
async def heartbeat(peer_id: str):
    if peer_id in PEERS:
        PEERS[peer_id]["last_seen"] = time.time()
        return {"message": "heartbeat received"}
    
    return {"error": "peer not found"}


@app.get("/peers")
async def get_peers(file: str = None):
    now = time.time()
    active_peers = []
    
    for peer_id, info in PEERS.items():
        if now - info["last_seen"] > TIL:
            del PEERS[peer_id]  # Remove stale peer
            continue
        
        if file is None or file in info["files"]:
            active_peers.append({
                "peer_id": peer_id,
                "ip": info["ip"],
                "port": info["port"],
                "files": info["files"]
            })
    
    return {"peers": active_peers}


