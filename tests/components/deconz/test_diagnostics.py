"""Test deCONZ diagnostics."""

from pydeconz.websocket import State

from homeassistant.components.deconz.const import CONF_MASTER_GATEWAY
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, Platform

from .test_gateway import HOST, PORT, setup_deconz_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(
    hass, hass_client, aioclient_mock, mock_deconz_websocket
):
    """Test config entry diagnostics."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    await mock_deconz_websocket(state=State.RUNNING)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "config": {
            "data": {CONF_API_KEY: REDACTED, CONF_HOST: HOST, CONF_PORT: PORT},
            "disabled_by": None,
            "domain": "deconz",
            "entry_id": "1",
            "options": {CONF_MASTER_GATEWAY: True},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "title": "Mock Title",
            "unique_id": REDACTED,
            "version": 1,
        },
        "deconz_config": {
            "bridgeid": REDACTED,
            "ipaddress": HOST,
            "mac": REDACTED,
            "modelid": "deCONZ",
            "name": "deCONZ mock gateway",
            "sw_version": "2.05.69",
            "uuid": "1234",
            "websocketport": 1234,
        },
        "websocket_state": State.RUNNING.value,
        "deconz_ids": {},
        "entities": {
            str(Platform.ALARM_CONTROL_PANEL): [],
            str(Platform.BINARY_SENSOR): [],
            str(Platform.BUTTON): [],
            str(Platform.CLIMATE): [],
            str(Platform.COVER): [],
            str(Platform.FAN): [],
            str(Platform.LIGHT): [],
            str(Platform.LOCK): [],
            str(Platform.NUMBER): [],
            str(Platform.SCENE): [],
            str(Platform.SELECT): [],
            str(Platform.SENSOR): [],
            str(Platform.SIREN): [],
            str(Platform.SWITCH): [],
        },
        "events": {},
        "alarm_systems": {},
        "groups": {},
        "lights": {},
        "scenes": {},
        "sensors": {},
    }
