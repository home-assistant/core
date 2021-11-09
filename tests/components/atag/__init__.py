"""Tests for the Atag integration."""

from homeassistant.components.atag import DOMAIN, AtagException
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 10000,
}
UID = "xxxx-xxxx-xxxx_xx-xx-xxx-xxx"
AUTHORIZED = 2
UNAUTHORIZED = 3
PAIR_REPLY = {"pair_reply": {"status": {"device_id": UID}, "acc_status": AUTHORIZED}}
UPDATE_REPLY = {
    "update_reply": {"status": {"device_id": UID}, "acc_status": AUTHORIZED}
}
RECEIVE_REPLY = {
    "retrieve_reply": {
        "status": {"device_id": UID},
        "report": {
            "burning_hours": 1000,
            "room_temp": 20,
            "outside_temp": 15,
            "dhw_water_temp": 30,
            "ch_water_temp": 40,
            "ch_water_pres": 1.8,
            "ch_return_temp": 35,
            "boiler_status": 0,
            "tout_avg": 12,
            "details": {"rel_mod_level": 0},
        },
        "control": {
            "ch_control_mode": 0,
            "ch_mode": 1,
            "ch_mode_duration": 0,
            "ch_mode_temp": 12,
            "dhw_temp_setp": 40,
            "dhw_mode": 1,
            "dhw_mode_temp": 150,
            "weather_status": 8,
        },
        "configuration": {
            "download_url": "http://firmware.atag-one.com:80/R58",
            "temp_unit": 0,
            "dhw_max_set": 65,
            "dhw_min_set": 40,
        },
        "acc_status": AUTHORIZED,
    }
}


def mock_connection(
    aioclient_mock: AiohttpClientMocker, authorized=True, conn_error=False
) -> None:
    """Mock the requests to Atag endpoint."""
    if conn_error:
        aioclient_mock.post(
            "http://127.0.0.1:10000/pair",
            exc=AtagException,
        )
        aioclient_mock.post(
            "http://127.0.0.1:10000/retrieve",
            exc=AtagException,
        )
        return
    PAIR_REPLY["pair_reply"].update(
        {"acc_status": AUTHORIZED if authorized else UNAUTHORIZED}
    )
    RECEIVE_REPLY["retrieve_reply"].update(
        {"acc_status": AUTHORIZED if authorized else UNAUTHORIZED}
    )
    aioclient_mock.post(
        "http://127.0.0.1:10000/retrieve",
        json=RECEIVE_REPLY,
    )
    aioclient_mock.post(
        "http://127.0.0.1:10000/update",
        json=UPDATE_REPLY,
    )
    aioclient_mock.post(
        "http://127.0.0.1:10000/pair",
        json=PAIR_REPLY,
    )


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Atag integration in Home Assistant."""
    mock_connection(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
