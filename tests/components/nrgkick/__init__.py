"""Tests for the NRGkick integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def async_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, *, add_to_hass: bool = True
) -> None:
    """Set up the component for tests."""
    if add_to_hass:
        config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def create_mock_config_entry(
    domain: str = DOMAIN,
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    entry_id: str = "test_entry",
    title: str = "NRGkick",
    unique_id: str = "TEST123456",
) -> MockConfigEntry:
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain=domain,
        data=data or {},
        options=options or {},
        entry_id=entry_id,
        title=title,
        unique_id=unique_id,
    )


__all__ = [
    "async_setup_integration",
    "create_mock_config_entry",
]
