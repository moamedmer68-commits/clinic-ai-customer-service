import hashlib

def make_thread_id(id_number: int, session_id: str) -> str:
    """Create a stable checkpoint key scoped to a patient without storing the ID in clear text."""
    raw_key = f"{id_number}:{session_id}".encode("utf-8")
    return hashlib.sha256(raw_key).hexdigest()
