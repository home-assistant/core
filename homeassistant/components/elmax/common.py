"""Elmax integration common classes and utilities."""

from __future__ import annotations

import ssl

from elmax_api.model.panel import PanelEntry
from packaging import version

from .const import ELMAX_LOCAL_API_PATH, MIN_APIV2_SUPPORTED_VERSION


def get_direct_api_url(host: str, port: int, use_ssl: bool) -> str:
    """Return the direct API url given the base URI."""
    schema = "https" if use_ssl else "http"
    return f"{schema}://{host}:{port}/{ELMAX_LOCAL_API_PATH}"


def build_direct_ssl_context(cadata: str) -> ssl.SSLContext:
    """Create a custom SSL context for direct-api verification."""
    context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cadata=cadata)
    return context


def check_local_version_supported(api_version: str | None) -> bool:
    """Check whether the given API version is supported."""
    if api_version is None:
        return False
    return version.parse(api_version) >= version.parse(MIN_APIV2_SUPPORTED_VERSION)


class DirectPanel(PanelEntry):
    """Helper class for wrapping a directly accessed Elmax Panel."""

    def __init__(self, panel_uri):
        """Construct the object."""
        super().__init__(panel_uri, True, {})

    def get_name_by_user(self, username: str) -> str:
        """Return the panel name."""
        return f"Direct Panel {self.hash}"
