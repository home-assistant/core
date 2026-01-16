"""Backblaze B2 client with extended timeouts.

The b2sdk library uses class-level timeout attributes. To avoid modifying
global library state, we subclass the relevant classes to provide extended
timeouts suitable for backup operations involving large files.
"""

from b2sdk.v2 import B2Api as BaseB2Api, InMemoryAccountInfo
from b2sdk.v2.b2http import B2Http as BaseB2Http
from b2sdk.v2.session import B2Session as BaseB2Session

# Extended timeouts for Home Assistant backup operations
# Default CONNECTION_TIMEOUT is 46 seconds, which can be too short for slow connections
CONNECTION_TIMEOUT = 120  # 2 minutes

# Default TIMEOUT_FOR_UPLOAD is 128 seconds, which is too short for large backups
TIMEOUT_FOR_UPLOAD = 43200  # 12 hours


class B2Http(BaseB2Http):  # type: ignore[misc]
    """B2Http with extended timeouts for backup operations."""

    CONNECTION_TIMEOUT = CONNECTION_TIMEOUT
    TIMEOUT_FOR_UPLOAD = TIMEOUT_FOR_UPLOAD


class B2Session(BaseB2Session):  # type: ignore[misc]
    """B2Session using custom B2Http with extended timeouts."""

    B2HTTP_CLASS = B2Http


class B2Api(BaseB2Api):  # type: ignore[misc]
    """B2Api using custom session with extended timeouts."""

    SESSION_CLASS = B2Session


__all__ = ["B2Api", "InMemoryAccountInfo"]
