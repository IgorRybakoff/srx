"""Constants and opcodes for SRX Public v0.1 wire and transformation format."""

# Magic bytes for SRX v1 Record Container
MAGIC: bytes = b"SRXH1"

# Record Types
REC_SNAPSHOT: int = 0
REC_ZSTD_PATCH: int = 1
REC_BSDIFF: int = 2
REC_STRUCT: int = 3

# Logical Transformation Opcodes
OP_SET: int = 1
OP_ADD: int = 2
OP_REMOVE: int = 3
OP_LINSERT: int = 4
OP_LDELETE: int = 5
OP_LMOVE: int = 6
OP_LREORDER: int = 7
OP_SDELTA: int = 8

# Physical Transformation Encodings
E_RAW: int = 1
E_ZSTD: int = 2
E_CTX: int = 3

# Residual Types for Structural Records
RES_NONE: int = 0
RES_FORMAT_GAPS: int = 1
RES_PATCH: int = 2

# Fixed record header sizes (bytes)
# 5 magic + 32 ref_hash + 32 tgt_hash + 8 tgt_size + 1 rtype + 4 payload_len = 82 bytes
RECORD_CONTAINER_HEADER_SIZE: int = 82
# 4 transform_len + 1 res_type + 4 res_len = 9 bytes
STRUCTURAL_HEADER_SIZE: int = 9
