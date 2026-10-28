"""Test Chef iQ diagnostics."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.chef_iq.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import ADDRESS, CHEFIQ_STATUS_SERVICE_INFO, TITLE


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the diagnostics include the latest advertisement but not the title."""
    # A user-edited title may hold personal information; it must not be exported.
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, title="Backyard smoker")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, CHEFIQ_STATUS_SERVICE_INFO)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "address": ADDRESS,
        "advertisement": {
            "name": "CQ60",
            "rssi": -60,
            "source": "local",
            "manufacturer_data": {"1485": "0350c91465ca079a64201e010301007ac4"},
        },
    }


async def test_diagnostics_without_advertisement(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the diagnostics of an entry whose probe has not been seen yet."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, title=TITLE)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "address": ADDRESS,
        "advertisement": None,
    }
