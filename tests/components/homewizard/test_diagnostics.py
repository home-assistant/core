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
                "unique_meter_id": None,
                "active_tariff": None,
                "wifi_ssid": REDACTED,
                "wifi_strength": 100,
                "total_power_import_kwh": None,
                "total_power_import_t1_kwh": 1234.111,
                "total_power_import_t2_kwh": 5678.222,
                "total_power_import_t3_kwh": None,
                "total_power_import_t4_kwh": None,
                "total_power_export_kwh": None,
                "total_power_export_t1_kwh": 4321.333,
                "total_power_export_t2_kwh": 8765.444,
                "total_power_export_t3_kwh": None,
                "total_power_export_t4_kwh": None,
                "active_power_w": -123,
                "active_power_l1_w": -123,
                "active_power_l2_w": 456,
                "active_power_l3_w": 123.456,
                "active_voltage_l1_v": None,
                "active_voltage_l2_v": None,
                "active_voltage_l3_v": None,
                "active_current_l1_a": None,
                "active_current_l2_a": None,
                "active_current_l3_a": None,
                "active_frequency_hz": None,
                "voltage_sag_l1_count": None,
                "voltage_sag_l2_count": None,
                "voltage_sag_l3_count": None,
                "voltage_swell_l1_count": None,
                "voltage_swell_l2_count": None,
                "voltage_swell_l3_count": None,
                "any_power_fail_count": None,
                "long_power_fail_count": None,
                "active_power_average_w": None,
                "montly_power_peak_timestamp": None,
                "montly_power_peak_w": None,
                "total_gas_m3": 1122.333,
                "gas_timestamp": "2021-03-14T11:22:33",
                "gas_unique_id": None,
                "active_liter_lpm": 12.345,
                "total_liter_m3": 1234.567,
                "external_devices": None,
            },
            "state": {"power_on": True, "switch_lock": False, "brightness": 255},
            "system": {"cloud_enabled": True},
        },
    }
