import os
import hashlib

CHUNK_SIZE = 1024 * 1024  # 1 MB

def get_file_metadata(file_path):
    file_size = os.path.getsize(file_path)
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE  # ceil division
    file_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            file_hash.update(chunk)
            
    return {
        "filename": os.path.basename(file_path),
        "size": file_size,
        "chunksize": CHUNK_SIZE,
        "chunks": total_chunks,
        "hash": file_hash.hexdigest()
    }
    
def read_chunk(file_path, chunk_index):
    with open(file_path, "rb") as f:
        f.seek(chunk_index * CHUNK_SIZE)
        return f.read(CHUNK_SIZE)