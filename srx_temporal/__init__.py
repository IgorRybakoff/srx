"""
srx_temporal — Temporal / Evidence product layer for SRX.

Implements the public v0.1 temporal/evidence layer on top of the stable SRX core facade.

This package:
- does NOT modify SRX core algorithms;
- consumes core only through the CoreReconstructor protocol
  (see core_adapter.py);
- has no LLM dependency and no GUI.
"""

__all__ = ["errors", "models", "core_adapter", "cas", "temporal_index",
           "reconstructor", "ingest"]

from .evidence import EvidenceResolver
