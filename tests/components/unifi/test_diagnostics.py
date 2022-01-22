"""Test UniFi Network diagnostics."""

from homeassistant.components.unifi.device_tracker import CLIENT_TRACKER, DEVICE_TRACKER
from homeassistant.components.unifi.sensor import RX_SENSOR, TX_SENSOR, UPTIME_SENSOR
from homeassistant.components.unifi.switch import BLOCK_SWITCH, DPI_SWITCH, POE_SWITCH
from homeassistant.const import Platform

from .test_controller import setup_unifi_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client, aioclient_mock):
    """Test config entry diagnostics."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "config_entry": dict(config_entry.data),
        "site_role": "admin",
        "entities": {
            str(Platform.DEVICE_TRACKER): {
                CLIENT_TRACKER: [],
                DEVICE_TRACKER: [],
            },
            str(Platform.SENSOR): {
                RX_SENSOR: [],
                TX_SENSOR: [],
                UPTIME_SENSOR: [],
            },
            str(Platform.SWITCH): {
                BLOCK_SWITCH: [],
                DPI_SWITCH: [],
                POE_SWITCH: [],
            },
        },
        "clients": {},
        "devices": {},
        "dpi_apps": {},
        "dpi_groups": {},
        "wlans": {},
    }
