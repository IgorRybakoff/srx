"""SRX Record Container packing and unpacking (SRXH1 wire format)."""

import struct
from srx.core.constants import MAGIC, REC_STRUCT, RECORD_CONTAINER_HEADER_SIZE
from srx.core.varint import sha256


def create_record(
    ref: bytes | None,
    target: bytes,
    record_type: int,
    payload: bytes,
) -> bytes:
    """Pack an SRX record into canonical binary container wire format.
    
    Header structure (82 bytes):
    - Magic (5 bytes: 'SRXH1')
    - Reference SHA-256 (32 bytes, or zeroes if snapshot)
    - Target SHA-256 (32 bytes)
    - Target Uncompressed Size (8 bytes, uint64 big-endian)
    - Record Type (1 byte: 0=Snapshot, 1=ZstdPatch, 2=Bsdiff, 3=Struct)
    - Payload Length (4 bytes, uint32 big-endian)
    Followed by payload bytes.
    """
    ref_hash = sha256(ref) if ref is not None else b"\x00" * 32
    target_hash = sha256(target)
    target_size = len(target)
    
    header = (
        MAGIC
        + ref_hash
        + target_hash
        + struct.pack(">Q", target_size)
        + bytes([record_type])
        + struct.pack(">I", len(payload))
    )
    assert len(header) == RECORD_CONTAINER_HEADER_SIZE
    return header + payload


def parse_record(record: bytes) -> dict:
    """Parse SRX record binary container header and extract fields."""
    if len(record) < RECORD_CONTAINER_HEADER_SIZE:
        raise ValueError(f"Record too short: {len(record)} bytes (minimum {RECORD_CONTAINER_HEADER_SIZE})")
        
    if record[:5] != MAGIC:
        raise ValueError(f"Invalid SRX record magic: {record[:5]!r} (expected {MAGIC!r})")
        
    ref_hash = record[5:37]
    target_hash = record[37:69]
    target_size = struct.unpack(">Q", record[69:77])[0]
    record_type = record[77]
    payload_len = struct.unpack(">I", record[78:82])[0]
    
    expected_len = RECORD_CONTAINER_HEADER_SIZE + payload_len
    if len(record) < expected_len:
        raise ValueError(
            f"Record payload truncated: expected {payload_len} bytes, got {len(record) - RECORD_CONTAINER_HEADER_SIZE}"
        )
    if len(record) > expected_len:
        raise ValueError(
            f"Record has trailing bytes: expected total {expected_len}, got {len(record)}"
        )

    payload = record[RECORD_CONTAINER_HEADER_SIZE:expected_len]
    
    return {
        "magic": MAGIC,
        "ref_hash": ref_hash,
        "target_hash": target_hash,
        "target_size": target_size,
        "record_type": record_type,
        "payload_len": payload_len,
        "payload": payload,
    }


def encode_structural_payload(
    transform_bytes: bytes,
    residual_type: int,
    residual_bytes: bytes,
) -> bytes:
    """Pack inner payload for structural record (REC_STRUCT)."""
    return (
        struct.pack(">I", len(transform_bytes))
        + transform_bytes
        + bytes([residual_type])
        + struct.pack(">I", len(residual_bytes))
        + residual_bytes
    )


def decode_structural_payload(payload: bytes) -> tuple[bytes, int, bytes]:
    """Unpack inner payload of structural record.
    
    Returns (transform_bytes, residual_type, residual_bytes).
    """
    if len(payload) < 9:
        raise ValueError(f"Structural payload too short: {len(payload)} bytes")
        
    tl = struct.unpack(">I", payload[0:4])[0]
    offset = 4
    if len(payload) < offset + tl + 5:
        raise ValueError("Structural payload truncated at transform blob")
        
    transform_bytes = payload[offset : offset + tl]
    offset += tl
    
    residual_type = payload[offset]
    offset += 1
    
    rl = struct.unpack(">I", payload[offset : offset + 4])[0]
    offset += 4
    
    if len(payload) < offset + rl:
        raise ValueError("Structural payload truncated at residual blob")
        
    residual_bytes = payload[offset : offset + rl]
    
    return transform_bytes, residual_type, residual_bytes
