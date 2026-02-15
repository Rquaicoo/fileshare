import asyncio
from identity import get_peer_id, load_keys
from crypto import decrypt_session_key, generate_aes_key, encrypt_session_key, aes_encrypt, aes_decrypt
from protocol import HELLO, SESSION
from cryptography.hazmat.primitives import serialization

async def connect_to_peer(ip, port):
    private_key, public_key = load_keys()
    peer_id = get_peer_id(public_key)
    
    reader, writer = await asyncio.open_connection(ip, port)
    
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # write HELLO message with peer_id and public_key
    writer.write(HELLO + b"|" + peer_id.encode() + b"|" + public_key_pem)
    await writer.drain()
    
    data = await reader.read(4096)
    if not data.startswith(SESSION):
        print("Invalid protocol message. Handshake failed.")
        writer.close()
        return
    
    _, encrypted_key = data.split(b"|", 1)  
    aes_key = decrypt_session_key(private_key, encrypted_key)
    
    encrypted_message = await reader.read(4096) 
    message = aes_decrypt(aes_key, encrypted_message)
    print("Server says:", message.decode())
    
    writer.close()