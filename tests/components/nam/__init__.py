"""Tests for the Nettigo Air Monitor integration."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.nam.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_json_object_fixture

INCOMPLETE_NAM_DATA = {
    "software_version": "NAMF-2020-36",
    "sensordatavalues": [],
}


async def init_integration(
    hass: HomeAssistant, co2_sensor: bool = True
) -> MockConfigEntry:
    """Set up the Nettigo Air Monitor integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "10.10.2.3"},
    )

    nam_data = await async_load_json_object_fixture(hass, "nam_data.json", DOMAIN)

    if not co2_sensor:
        # Remove conc_co2_ppm value
        nam_data["sensordatavalues"].pop(6)

    update_response = Mock(json=AsyncMock(return_value=nam_data))

    with (
        patch(
            "homeassistant.components.nam.NettigoAirMonitor.async_get_mac_address",
            return_value="aa:bb:cc:dd:ee:ff",
        ),
        patch(
            "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
            return_value=update_response,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
