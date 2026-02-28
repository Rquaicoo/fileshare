import os, hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

"""
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
"""

def generate_aes_key():
    # generate a random 128-bit AES key used as the session key for encrypting file transfers
    return AESGCM.generate_key(bit_length=128)

def encrypt_session_key(public_key, aes_key: bytes):
    # encrypt the AES session key using the peer's public RSA key
    return public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def decrypt_session_key(private_key, encrypted_key: bytes):
    # decrypt the AES session key using the peer's private RSA key
    return private_key.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    
def aes_encrypt(aes_key: bytes, plaintext: bytes):
    # encrypt data using AES-GCM
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext  # prepend nonce for later use

def aes_decrypt(aes_key: bytes, ciphertext: bytes):
    # decrypt data using AES-GCM
    aesgcm = AESGCM(aes_key)
    nonce = ciphertext[:12]  # extract nonce
    ct = ciphertext[12:]  # extract actual ciphertext
    return aesgcm.decrypt(nonce, ct, None)