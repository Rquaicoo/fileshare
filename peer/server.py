import asyncio
import os
from .identity import get_peer_id, load_keys
from .crypto import aes_encrypt, generate_aes_key, encrypt_session_key, decrypt_session_key, aes_decrypt
from fastapi import FastAPI, Request
from .protocol import HELLO, SESSION
from cryptography.hazmat.primitives import serialization
from .chunk_manager import get_file_metadata, read_chunk

"""
Server-side logic for handling peer connections and the initial handshake protocol. 
This includes receiving the HELLO message, verifying the peer ID, generating an AES session key, encrypting it with the peer's public key, 
and sending it back in a SESSION message.

Peer A → Peer B:
    HELLO | peer_id | public_key

Peer B:
    - verifies peer_id matches public_key
    - generates AES session key
    - encrypts AES key with A’s public key

Peer B → Peer A:
    SESSION_KEY | encrypted_key

Both sides:
    - switch to AES encryption

HELLO: Initial message sent by a peer to initiate a connection. It includes the peer's ID and public key.
for example: HELLO|peer_id|public_key


- Files are split into fixed-size chunks
- Client requests specific chunk indexes
- Server sends encrypted chunks
- Client downloads chunks concurrently
- File is reassembled correctly
- Integrity is verified (SHA256)

OTHER MESSAGES: 
META|filename|filesize|chunksize|total_chunks|file_hash
GET|filename|chunk_index
CHUNK|chunk_index|bytes
DONE


"""
async def handle_peer(reader, writer, shared_dir="shared"):
    # Receive HELLO message with peer_id and public_key
    data = await reader.read(1024)
    if not data.startswith(HELLO):
        print("Invalid protocol message")
        writer.close()
        return
    
    
    _, peer_id, public_key_pem = data.split(b"|", 2)
    
    peer_public_key = serialization.load_pem_public_key(public_key_pem)
    
    # Generate AES session key and encrypt it with the peer's public key
    aes_key = generate_aes_key()
    encrypted_key = encrypt_session_key(public_key_pem, aes_key)
    
    # Send SESSION message with the encrypted AES key
    writer.write(SESSION + b"|" + encrypted_key)
    await writer.drain()
    
    print("Handshake completed with peer. Session now established.")
    await serve_file(reader, writer, aes_key, shared_dir)
    
async def start_server(port=9000, shared_dir="shared"):
    async def handler(reader, writer):
        await handle_peer(reader, writer, shared_dir)
    
    server = await asyncio.start_server(handler, "0.0.0.0", port)
    print(f"Server listening on port {port}")
    async with server:
        await server.serve_forever()
        
        
async def serve_file(reader, writer, aes_key, shared_dir="shared"):
    """Handle file transfer requests from peer."""
    try:
        while True:
            encrypted_message = await reader.read(4096)
            if not encrypted_message:
                break
                
            request = aes_decrypt(aes_key, encrypted_message).decode()
            print(f"Received request: {request}")
            
            if request.startswith("META"):
                _, filename = request.split("|", 1)
                file_path = os.path.join(shared_dir, filename)
                
                if not os.path.exists(file_path):
                    error_msg = f"ERROR|File not found: {filename}"
                    writer.write(aes_encrypt(aes_key, error_msg.encode()))
                    await writer.drain()
                    continue
                    
                meta = get_file_metadata(file_path)
                meta_msg = f"META|{meta['filename']}|{meta['size']}|{meta['chunksize']}|{meta['chunks']}|{meta['hash']}"
                writer.write(aes_encrypt(aes_key, meta_msg.encode()))
                await writer.drain()
                print(f"Sent metadata for {filename}")
                
            elif request.startswith("GET"):
                _, filename, chunk_index = request.split("|")
                chunk_index = int(chunk_index)
                file_path = os.path.join(shared_dir, filename)
                
                if not os.path.exists(file_path):
                    error_msg = f"ERROR|File not found: {filename}"
                    writer.write(aes_encrypt(aes_key, error_msg.encode()))
                    await writer.drain()
                    continue
                    
                data = read_chunk(file_path, chunk_index)
                payload = f"CHUNK|{chunk_index}|".encode() + data
                writer.write(aes_encrypt(aes_key, payload))
                await writer.drain()
                print(f"Sent chunk {chunk_index} of {filename}")
                
            elif request == "DONE":
                print("Peer finished downloading file.")
                writer.close()
                break
                
    except Exception as e:
        print(f"Error in serve_file: {e}")
        writer.close()