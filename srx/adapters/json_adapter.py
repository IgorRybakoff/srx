"""JSON Reference Format Adapter for SRX Public v0.1."""

import json
from typing import Any
from srx.core.diff import diff_json, diff_json_variants


class JSONAdapter:
    """Standard JSON Format Adapter implementing the SRX FormatAdapter interface."""

    @staticmethod
    def parse(raw_bytes: bytes) -> Any:
        """Parse raw bytes into Python structured data object."""
        return json.loads(raw_bytes.decode("utf-8"))

    @staticmethod
    def serialize(value: Any, pretty: bool = True) -> bytes:
        """Serialize structured data object into JSON bytes."""
        if pretty:
            return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def structural_diff(reference: Any, target: Any) -> list[tuple]:
        """Compute standard deterministic structural diff."""
        return diff_json(reference, target)

    @staticmethod
    def structural_diff_variants(reference: Any, target: Any) -> list[tuple[str, list[tuple]]]:
        """Compute all structural candidate diff variants."""
        return diff_json_variants(reference, target)
