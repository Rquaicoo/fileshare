"""
Integrated runner for the P2P file sharing system.
Starts the discovery service and peer server, allowing file uploads and downloads.
"""

import asyncio
import os
import sys
import argparse

# Add project root to path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from peer.identity import load_keys, get_peer_id
from peer.server import start_server
from peer.client import download_from_discovery
import httpx
import uvicorn
from peer.main import app as discovery_app
from threading import Thread
import time


async def register_peer(discovery_url, peer_id, public_key_pem, port, shared_dir="shared"):
    """Register this peer with the discovery service."""
    files = []
    if os.path.exists(shared_dir):
        files = os.listdir(shared_dir)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "peer_id": peer_id,
                "public_key": public_key_pem.decode('utf-8'),
                "port": port,
                "files": files
            }
            response = await client.post(f"{discovery_url}/register", json=payload)
            print(f"Registered with discovery service: {response.json()}")
            return True
    except Exception as e:
        print(f"Failed to register with discovery service: {e}")
        return False


async def heartbeat_loop(discovery_url, peer_id, interval=30):
    """Send periodic heartbeats to keep peer registered."""
    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{discovery_url}/heartbeat", params={"peer_id": peer_id})
                print(f"Heartbeat sent: {response.json()}")
        except Exception as e:
            print(f"Heartbeat failed: {e}")
        
        await asyncio.sleep(interval)


async def main():
    parser = argparse.ArgumentParser(description="P2P File Sharing System")
    parser.add_argument("--mode", choices=["discovery", "peer", "client", "full"], default="full",
                        help="Mode to run in (default: full)")
    parser.add_argument("--discovery-host", default="localhost", help="Discovery service host")
    parser.add_argument("--discovery-port", type=int, default=8000, help="Discovery service port")
    parser.add_argument("--peer-port", type=int, default=9000, help="Peer server port")
    parser.add_argument("--shared-dir", default="shared", help="Directory for shared files")
    parser.add_argument("--download-file", help="File to download (client mode)")
    parser.add_argument("--output-dir", default="downloads", help="Directory to save downloaded files")
    
    args = parser.parse_args()
    
    discovery_url = f"http://{args.discovery_host}:{args.discovery_port}"
    
    if args.mode == "discovery":
        # Run only the discovery service
        print(f"Starting discovery service on {args.discovery_host}:{args.discovery_port}")
        uvicorn.run(discovery_app, host=args.discovery_host, port=args.discovery_port, log_level="info")
    
    elif args.mode == "peer":
        # Run only the peer server
        private_key, public_key = load_keys()
        peer_id = get_peer_id(public_key)
        
        print(f"Peer ID: {peer_id[:16]}...")
        print(f"Starting peer server on port {args.peer_port}")
        
        os.makedirs(args.shared_dir, exist_ok=True)
        await start_server(args.peer_port, args.shared_dir)
    
    elif args.mode == "client":
        # Run client to download a file
        if not args.download_file:
            print("Error: --download-file is required for client mode")
            sys.exit(1)
        
        print(f"Downloading {args.download_file} from discovery service at {discovery_url}")
        success = await download_from_discovery(discovery_url, args.download_file, args.output_dir)
        sys.exit(0 if success else 1)
    
    elif args.mode == "full":
        # Run discovery service in a background thread
        private_key, public_key = load_keys()
        peer_id = get_peer_id(public_key)
        
        from cryptography.hazmat.primitives import serialization
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        print("=" * 60)
        print("P2P FILE SHARING SYSTEM - FULL MODE")
        print("=" * 60)
        print(f"Peer ID: {peer_id[:16]}...")
        print(f"Discovery Service: {discovery_url}")
        print(f"Peer Server: localhost:{args.peer_port}")
        print(f"Shared Directory: {args.shared_dir}")
        print("=" * 60)
        
        # Start discovery service in background thread
        def run_discovery():
            uvicorn.run(discovery_app, host=args.discovery_host, port=args.discovery_port,
                       log_level="error", access_log=False)
        
        discovery_thread = Thread(target=run_discovery, daemon=True)
        discovery_thread.start()
        
        # Wait for discovery service to start
        await asyncio.sleep(2)
        
        # Register this peer
        success = await register_peer(discovery_url, peer_id, public_key_pem, args.peer_port, args.shared_dir)
        if not success:
            print("Continuing anyway...")
        
        # Start heartbeat and peer server tasks
        os.makedirs(args.shared_dir, exist_ok=True)
        
        heartbeat_task = asyncio.create_task(heartbeat_loop(discovery_url, peer_id, interval=30))
        server_task = asyncio.create_task(start_server(args.peer_port, args.shared_dir))
        
        try:
            await asyncio.gather(heartbeat_task, server_task)
        except KeyboardInterrupt:
            print("\nShutting down...")
            heartbeat_task.cancel()
            server_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
