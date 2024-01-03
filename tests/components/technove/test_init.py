"""Tests for the TechnoVE integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setting_unique_id(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test we set unique ID if not set yet."""
    assert init_integration.unique_id == "AA:AA:AA:AA:AA:BB"
