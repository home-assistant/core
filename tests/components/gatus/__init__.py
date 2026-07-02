"""Tests for the Gatus integration."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_data: list[dict[str, Any]],
    entry_id: str | None = None,
) -> MockConfigEntry:
    """Handle repetitive config entry setup sequences with explicit mock data."""
    mock_gatus_client.get_endpoints_statuses.return_value = mock_data

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "http://gatus.local:80"},
        entry_id=entry_id or "1234567890abcdef1234567890abcdef",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
