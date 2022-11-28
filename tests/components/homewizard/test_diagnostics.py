"""Tests for diagnostics data."""
from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
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
        "entry": {"ip_address": REDACTED},
        "data": {
            "device": {
                "product_name": "P1 Meter",
                "product_type": "HWE-P1",
                "serial": REDACTED,
                "api_version": "v1",
                "firmware_version": "2.11",
            },
            "data": {
                "smr_version": 50,
                "meter_model": "ISKRA  2M550T-101",
                "wifi_ssid": REDACTED,
                "wifi_strength": 100,
                "total_power_import_t1_kwh": 1234.111,
                "total_power_import_t2_kwh": 5678.222,
                "total_power_export_t1_kwh": 4321.333,
                "total_power_export_t2_kwh": 8765.444,
                "active_power_w": -123,
                "active_power_l1_w": -123,
                "active_power_l2_w": 456,
                "active_power_l3_w": 123.456,
                "total_gas_m3": 1122.333,
                "gas_timestamp": "2021-03-14T11:22:33",
                "active_liter_lpm": 12.345,
                "total_liter_m3": 1234.567,
            },
            "state": {"power_on": True, "switch_lock": False, "brightness": 255},
        },
    }
