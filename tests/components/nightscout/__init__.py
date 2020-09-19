"""Tests for the Nightscout integration."""
import json

from aiohttp import ClientConnectionError
from py_nightscout.models import SGV, ServerStatus

from homeassistant.components.nightscout.const import DOMAIN
from homeassistant.const import CONF_URL

from tests.async_mock import patch
from tests.common import MockConfigEntry

GLUCOSE_READINGS = [
    SGV.new_from_json_dict(
        json.loads(
            '{"_id":"5f2b01f5c3d0ac7c4090e223","device":"xDrip-LimiTTer","date":1596654066533,"dateString":"2020-08-05T19:01:06.533Z","sgv":169,"delta":-5.257,"direction":"FortyFiveDown","type":"sgv","filtered":182823.5157,"unfiltered":182823.5157,"rssi":100,"noise":1,"sysTime":"2020-08-05T19:01:06.533Z","utcOffset":-180}'
        )
    )
]
SERVER_STATUS = ServerStatus.new_from_json_dict(
    json.loads(
        '{"status":"ok","name":"nightscout","version":"13.0.1","serverTime":"2020-08-05T18:14:02.032Z","serverTimeEpoch":1596651242032,"apiEnabled":true,"careportalEnabled":true,"boluscalcEnabled":true,"settings":{},"extendedSettings":{},"authorized":null}'
    )
)


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Nightscout integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://some.url:1234"},
    )
    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
        return_value=GLUCOSE_READINGS,
    ), patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
        return_value=SERVER_STATUS,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def init_integration_unavailable(hass) -> MockConfigEntry:
    """Set up the Nightscout integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://some.url:1234"},
    )
    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
        side_effect=ClientConnectionError(),
    ), patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
        return_value=SERVER_STATUS,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def init_integration_empty_response(hass) -> MockConfigEntry:
    """Set up the Nightscout integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://some.url:1234"},
    )
    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_sgvs", return_value=[]
    ), patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
        return_value=SERVER_STATUS,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
