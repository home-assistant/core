"""Tests for the NRGkick integration."""

from __future__ import annotations

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
    domain=DOMAIN,
    data=None,
    options=None,
    entry_id="test_entry",
    title="NRGkick",
    unique_id="TEST123456",
):
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
