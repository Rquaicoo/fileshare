import asyncio
from identity import get_peer_id, load_keys
from crypto import aes_encrypt, generate_aes_key, encrypt_session_key, decrypt_session_key
from fastapi import FastAPI, Request
from protocol import HELLO, SESSION
from cryptography.hazmat.primitives import serialization

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

"""
async def handle_peer(reader, writer):
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
    
    
    # Example encrypted response to the peer (you would replace this with actual file transfer logic)
    msg = aes_encrypt(aes_key, b"READY")
    writer.write(msg)
    await writer.drain()
    
async def start_server(port=9000):
    server = await asyncio.start_server(handle_peer, "0.0.0.0", port)
    print(f"Server listening on port {port}")
    async with server:
        await server.serve_forever()