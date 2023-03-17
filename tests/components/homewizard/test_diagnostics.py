"""Tests for diagnostics data."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
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
                "wifi_ssid": REDACTED,
                "wifi_strength": 100,
                "smr_version": 50,
                "meter_model": "ISKRA  2M550T-101",
                "unique_meter_id": REDACTED,
                "active_tariff": 2,
                "total_power_import_kwh": 13779.338,
                "total_power_import_t1_kwh": 10830.511,
                "total_power_import_t2_kwh": 2948.827,
                "total_power_import_t3_kwh": None,
                "total_power_import_t4_kwh": None,
                "total_power_export_kwh": 13086.777,
                "total_power_export_t1_kwh": 4321.333,
                "total_power_export_t2_kwh": 8765.444,
                "total_power_export_t3_kwh": None,
                "total_power_export_t4_kwh": None,
                "active_power_w": -123,
                "active_power_l1_w": -123,
                "active_power_l2_w": 456,
                "active_power_l3_w": 123.456,
                "active_voltage_l1_v": 230.111,
                "active_voltage_l2_v": 230.222,
                "active_voltage_l3_v": 230.333,
                "active_current_l1_a": -4,
                "active_current_l2_a": 2,
                "active_current_l3_a": 0,
                "active_frequency_hz": 50,
                "voltage_sag_l1_count": 1,
                "voltage_sag_l2_count": 2,
                "voltage_sag_l3_count": 3,
                "voltage_swell_l1_count": 4,
                "voltage_swell_l2_count": 5,
                "voltage_swell_l3_count": 6,
                "any_power_fail_count": 4,
                "long_power_fail_count": 5,
                "active_power_average_w": 123.0,
                "monthly_power_peak_w": 1111.0,
                "monthly_power_peak_timestamp": "2023-01-01T08:00:10",
                "total_gas_m3": 1122.333,
                "gas_timestamp": "2021-03-14T11:22:33",
                "gas_unique_id": REDACTED,
                "active_liter_lpm": 12.345,
                "total_liter_m3": 1234.567,
                "external_devices": None,
            },
            "state": {"power_on": True, "switch_lock": False, "brightness": 255},
            "system": {"cloud_enabled": True},
        },
    }
