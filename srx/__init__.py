"""SRX Public v0.1: Exact reconstruction and version intelligence for evolving structured data."""

__version__ = "0.1.0"
__author__ = "SRX Contributors"
__license__ = "Apache-2.0"

from srx.adapters.json_adapter import JSONAdapter
from srx.reconstruct.reconstructor import SRXReconstructor
from srx.reconstruct.verifier import SRXVerifier
from srx.public_api import SRXCoreAPI

__all__ = [
    "JSONAdapter",
    "SRXReconstructor",
    "SRXVerifier",
    "SRXCoreAPI",
    "__version__",
]
