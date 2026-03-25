"""Helper functions for testing the Span Panel integration."""

from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_SCAN_INTERVAL

from tests.common import MockConfigEntry


def make_span_panel_entry(
    entry_id: str = "test_entry",
    host: str = "192.168.1.100",
    access_token: str = "test_token",
    scan_interval: int = 15,
    options: dict[str, Any] | None = None,
    version: int = 2,
    unique_id: str | None = None,
) -> MockConfigEntry:
    """Create a MockConfigEntry for Span Panel with common defaults."""
    return MockConfigEntry(
        domain="span_panel",
        data={
            CONF_HOST: host,
            CONF_ACCESS_TOKEN: access_token,
            CONF_SCAN_INTERVAL: scan_interval,
        },
        options=options or {},
        entry_id=entry_id,
        version=version,
        unique_id=unique_id or f"{host}_{entry_id}",
    )
