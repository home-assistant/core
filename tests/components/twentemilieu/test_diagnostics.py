"""Tests for the diagnostics data provided by the TwenteMilieu integration."""
from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
):
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "WasteType.NON_RECYCLABLE": ["2021-11-01", "2021-12-01"],
        "WasteType.ORGANIC": ["2021-11-02"],
        "WasteType.PAPER": [],
        "WasteType.TREE": ["2022-01-06"],
        "WasteType.PACKAGES": ["2021-11-03"],
    }
