"""Tests for the diagnostics data provided by the Elgato integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "info": {
            "display_name": "Frenck",
            "firmware_build_number": 192,
            "firmware_version": "1.0.3",
            "hardware_board_type": 53,
            "mac_address": None,
            "product_name": "Elgato Key Light",
            "serial_number": "CN11A1A00001",
            "wifi": None,
            "features": ["lights"],
        },
        "state": {
            "on": True,
            "brightness": 21,
            "hue": None,
            "saturation": None,
            "temperature": 297,
        },
    }
