"""Test deCONZ diagnostics."""

from unittest.mock import patch

from pydeconz.websocket import STATE_RUNNING

from homeassistant.const import Platform

from .test_gateway import DECONZ_CONFIG, setup_deconz_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(
    hass, hass_client, aioclient_mock, mock_deconz_websocket
):
    """Test config entry diagnostics."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    await mock_deconz_websocket(state=STATE_RUNNING)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.helpers.system_info.async_get_system_info",
        return_value={"get_system_info": "fake data"},
    ):
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry
        ) == {
            "home_assistant": {"get_system_info": "fake data"},
            "config_entry": dict(config_entry.data),
            "deconz_config": DECONZ_CONFIG,
            "websocket_state": STATE_RUNNING,
            "deconz_ids": {},
            "entities": {
                str(Platform.ALARM_CONTROL_PANEL): [],
                str(Platform.BINARY_SENSOR): [],
                str(Platform.CLIMATE): [],
                str(Platform.COVER): [],
                str(Platform.FAN): [],
                str(Platform.LIGHT): [],
                str(Platform.LOCK): [],
                str(Platform.NUMBER): [],
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
