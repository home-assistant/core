"""Test Wireless Sensor Tag diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    # Check that diagnostics data is present
    assert "entry_data" in diagnostics
    assert "data" in diagnostics

    # Check that sensitive data is redacted
    entry_data = diagnostics["entry_data"]
    assert isinstance(entry_data, dict)
    assert (
        entry_data.get("username") == "test@example.com"
    )  # Username should be present
    assert "password" not in entry_data or entry_data.get("password") == "**REDACTED**"

    # Check that tag data is present
    data = diagnostics["data"]
    assert isinstance(data, dict)
    assert len(data) > 0

    # Check transformed tag data structure
    for tag_data in data.values():
        assert isinstance(tag_data, dict)
        # Check that transformed data has expected keys
        assert "uuid" in tag_data
        assert "name" in tag_data
        assert "is_alive" in tag_data
        assert "battery" in tag_data  # Transformed battery field
