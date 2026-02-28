import asyncio
import os
import hashlib
from .identity import get_peer_id, load_keys
from .crypto import decrypt_session_key, aes_encrypt, aes_decrypt
from .protocol import HELLO, SESSION
from cryptography.hazmat.primitives import serialization
import httpx

# Maximum concurrent chunk downloads
MAX_CONCURRENT_CHUNKS = 4
# Timeout for connections (increased for large files)
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30


async def get_file_metadata(ip, port, filename):
    """Get file metadata from a peer."""
    private_key, public_key = load_keys()
    peer_id = get_peer_id(public_key)
    
    try:
        print(f"[METADATA] Connecting to {ip}:{port}...")
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=CONNECT_TIMEOUT
        )
        
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        hello_msg = HELLO + b"|" + peer_id.encode() + b"|" + public_key_pem
        writer.write(hello_msg)
        await writer.drain()
        
        data = await reader.read(4096)
        if not data.startswith(SESSION):
            return None, None
        
        _, encrypted_key = data.split(b"|", 1)
        aes_key = decrypt_session_key(private_key, encrypted_key)
        
        # Request metadata
        meta_request = f"META|{filename}"
        writer.write(aes_encrypt(aes_key, meta_request.encode()))
        await writer.drain()
        
        encrypted_meta = await reader.read(4096)
        meta_response = aes_decrypt(aes_key, encrypted_meta).decode()
        
        writer.close()
        await writer.wait_closed()
        
        if meta_response.startswith("ERROR"):
            return None, None
            
        parts = meta_response.split("|")
        if len(parts) < 6:
            return None, None
        
        # Return metadata and AES key for this file
        meta = {
            "filename": parts[1],
            "file_size": int(parts[2]),
            "chunk_size": int(parts[3]),
            "total_chunks": int(parts[4]),
            "hash": parts[5]
        }
        
        return meta, None  # We'll establish new connections for chunks
        
    except Exception as e:
        print(f"Error getting metadata: {e}")
        return None, None


async def download_single_chunk(ip, port, filename, chunk_index):
    """Download a single chunk by establishing a new connection."""
    private_key, public_key = load_keys()
    peer_id = get_peer_id(public_key)
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=CONNECT_TIMEOUT
        )
        
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        hello_msg = HELLO + b"|" + peer_id.encode() + b"|" + public_key_pem
        writer.write(hello_msg)
        await writer.drain()
        
        data = await reader.read(4096)
        if not data.startswith(SESSION):
            return None
        
        _, encrypted_key = data.split(b"|", 1)
        aes_key = decrypt_session_key(private_key, encrypted_key)
        
        # Request chunk
        get_request = f"GET|{filename}|{chunk_index}"
        writer.write(aes_encrypt(aes_key, get_request.encode()))
        await writer.drain()
        
        encrypted_chunk = await reader.read(1024 * 1024 + 100)
        chunk_data = aes_decrypt(aes_key, encrypted_chunk)
        
        writer.close()
        await writer.wait_closed()
        
        # Parse CHUNK|index|data format
        chunk_parts = chunk_data.split(b"|", 2)
        if len(chunk_parts) >= 3 and chunk_parts[0] == b"CHUNK":
            return chunk_parts[2]
        
        return None
        
    except Exception as e:
        print(f"Error downloading chunk {chunk_index}: {e}")
        return None


async def connect_to_peer(ip, port, filename, output_dir="downloads"):
    """Connect to a peer and download a file with concurrent chunk downloads."""
    try:
        print(f"[DOWNLOAD] Connecting to peer at {ip}:{port}")
        print(f"[DOWNLOAD] Downloading file: {filename}")
        
        # Get metadata
        meta, _ = await get_file_metadata(ip, port, filename)
        if not meta:
            print(f"[ERROR] Failed to get metadata for {filename}")
            print(f"[ERROR] Peer at {ip}:{port} may be offline or file doesn't exist")
            return False
        
        fname = meta["filename"]
        file_size = meta["file_size"]
        total_chunks = meta["total_chunks"]
        file_hash = meta["hash"]
        
        print(f"File metadata: {fname} ({file_size} bytes, {total_chunks} chunks)")
        
        # Download chunks concurrently
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, fname)
        
        chunks = {}
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHUNKS)
        
        async def download_chunk(index):
            """Download a single chunk from the peer."""
            async with semaphore:
                chunk_data = await download_single_chunk(ip, port, filename, index)
                if chunk_data:
                    chunks[index] = chunk_data
                    print(f"Downloaded chunk {index}/{total_chunks}")
                    return True
                return False
        
        # Create tasks for all chunks
        tasks = [download_chunk(i) for i in range(total_chunks)]
        results = await asyncio.gather(*tasks)
        
        if not all(results):
            print("Some chunks failed to download")
            return False
        
        # Reassemble file
        print("Reassembling file...")
        file_hash_obj = hashlib.sha256()
        
        with open(output_path, "wb") as f:
            for i in range(total_chunks):
                if i not in chunks:
                    print(f"Missing chunk {i}")
                    return False
                f.write(chunks[i])
                file_hash_obj.update(chunks[i])
        
        # Verify integrity
        calculated_hash = file_hash_obj.hexdigest()
        if calculated_hash == file_hash:
            print(f"✓ File downloaded successfully and verified: {output_path}")
            return True
        else:
            print(f"✗ Hash mismatch! Expected {file_hash}, got {calculated_hash}")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False


async def download_from_discovery(discovery_url, filename, output_dir="downloads"):
    """Find peers with a file and download from the first available one."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Query discovery service for peers with this file
            response = await client.get(f"{discovery_url}/peers", params={"file": filename})
            peers_data = response.json()
            
            if not peers_data.get("peers"):
                print(f"No peers found with file: {filename}")
                return False
            
            peers = peers_data["peers"]
            print(f"Found {len(peers)} peer(s) with {filename}")
            
            # Try each peer until successful
            for peer in peers:
                peer_id = peer["peer_id"]
                ip = peer["ip"]
                port = peer["port"]
                
                print(f"Trying to download from peer {peer_id[:8]}... at {ip}:{port}")
                success = await connect_to_peer(ip, port, filename, output_dir)
                
                if success:
                    return True
            
            print("Failed to download from all available peers")
            return False
            
    except Exception as e:
        print(f"Error querying discovery service: {e}")
        return False


async def main():
    """Example usage."""
    discovery_url = "http://localhost:8000"  # Discovery service URL
    filename = "test.txt"
    
    await download_from_discovery(discovery_url, filename)


if __name__ == "__main__":
    asyncio.run(main())