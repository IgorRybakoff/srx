"""Public SRX core boundary for the temporal/evidence layer."""

from __future__ import annotations

from typing import Protocol

from .cas import sha256_hex
from .errors import HashMismatch


class CoreReconstructor(Protocol):
    def reconstruct(self, reference: bytes | None, representation: bytes) -> bytes: ...
    def verify(self, reconstructed: bytes, expected_sha256: str) -> bool: ...


class CoreCodec(CoreReconstructor, Protocol):
    def encode(self, reference: bytes | None, target: bytes) -> bytes: ...
    def requires_reference(self, representation: bytes) -> bool: ...


class StubCoreReconstructor:
    """Exact full-copy stand-in used only by isolated temporal unit tests."""

    def encode(self, reference: bytes | None, target: bytes) -> bytes:
        return target

    def requires_reference(self, representation: bytes) -> bool:
        return False

    def reconstruct(self, reference: bytes | None, representation: bytes) -> bytes:
        return representation

    def verify(self, reconstructed: bytes, expected_sha256: str) -> bool:
        return sha256_hex(reconstructed) == expected_sha256


class ThinCoreAdapter:
    """Thin public-method adapter; temporal code never imports private core internals."""

    def __init__(
        self,
        real_core,
        reconstruct_attr: str = "reconstruct",
        verify_attr: str = "verify",
        encode_attr: str = "encode",
        requires_reference_attr: str = "requires_reference",
    ):
        self._reconstruct = getattr(real_core, reconstruct_attr)
        self._verify = getattr(real_core, verify_attr)
        self._encode = getattr(real_core, encode_attr, None)
        self._requires_reference = getattr(real_core, requires_reference_attr, None)

    def encode(self, reference: bytes | None, target: bytes) -> bytes:
        if self._encode is None:
            raise NotImplementedError("core does not expose public encode()")
        return self._encode(reference, target)

    def requires_reference(self, representation: bytes) -> bool:
        if self._requires_reference is None:
            raise NotImplementedError("core does not expose requires_reference()")
        return bool(self._requires_reference(representation))

    def reconstruct(self, reference: bytes | None, representation: bytes) -> bytes:
        return self._reconstruct(reference, representation)

    def verify(self, reconstructed: bytes, expected_sha256: str) -> bool:
        return self._verify(reconstructed, expected_sha256)


def verify_or_raise(
    reconstructor: CoreReconstructor,
    data: bytes,
    expected_sha256: str,
    context: str = "",
) -> None:
    if not reconstructor.verify(data, expected_sha256):
        raise HashMismatch(expected_sha256, sha256_hex(data), context)


def make_production_core() -> CoreCodec:
    """Wire the temporal layer to the real public SRXCoreAPI facade."""
    from srx.public_api import SRXCoreAPI

    return ThinCoreAdapter(SRXCoreAPI())
