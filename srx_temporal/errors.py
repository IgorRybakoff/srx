"""
Explicit typed errors for the temporal / evidence layer.

Integrity failures are errors, never warnings (contract section 12).
No silent best-effort fallback is permitted anywhere in this package.
"""


class SRXTemporalError(Exception):
    """Base class for all temporal-layer errors."""


class VersionNotFound(SRXTemporalError):
    def __init__(self, version_id: str):
        super().__init__(f"version not found: {version_id!r}")
        self.version_id = version_id


class FileNotFoundInVersion(SRXTemporalError):
    def __init__(self, version_id: str, path: str):
        super().__init__(f"file {path!r} not found in version {version_id!r}")
        self.version_id = version_id
        self.path = path


class KeyNotFoundInVersion(SRXTemporalError):
    def __init__(self, version_id: str, path: str, key_path: str):
        super().__init__(
            f"key {key_path!r} not found in {path!r} at version {version_id!r}"
        )
        self.version_id = version_id
        self.path = path
        self.key_path = key_path


class MissingReference(SRXTemporalError):
    def __init__(self, ref: str):
        super().__init__(f"referenced representation not found: {ref!r}")
        self.ref = ref


class CorruptRepresentation(SRXTemporalError):
    def __init__(self, ref: str, detail: str = ""):
        msg = f"representation is corrupt: {ref!r}"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)
        self.ref = ref


class HashMismatch(SRXTemporalError):
    def __init__(self, expected: str, actual: str, context: str = ""):
        msg = f"hash mismatch: expected {expected!r}, got {actual!r}"
        if context:
            msg += f" [{context}]"
        super().__init__(msg)
        self.expected = expected
        self.actual = actual


class InvalidEvidence(SRXTemporalError):
    def __init__(self, reason: str):
        super().__init__(f"invalid evidence: {reason}")
        self.reason = reason


class TemporalOrderError(SRXTemporalError):
    def __init__(self, reason: str):
        super().__init__(f"temporal order error: {reason}")
        self.reason = reason
