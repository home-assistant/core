"""Tests for the Tesla Wall Connector diagnostics."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from tesla_wall_connector.wall_connector import Lifetime, Vitals, WifiStatus

from homeassistant.core import HomeAssistant

from .conftest import create_wall_connector_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = await create_wall_connector_entry(
        hass,
        vitals_data=Vitals(
            {
                "contactor_closed": True,
                "vehicle_connected": True,
                "session_s": 3600,
                "grid_v": 230.1,
                "grid_hz": 50.02,
                "vehicle_current_a": 16.0,
                "currentA_a": 16.0,
                "currentB_a": 15.9,
                "currentC_a": 16.1,
                "currentN_a": 0.0,
                "voltageA_v": 230.1,
                "voltageB_v": 231.0,
                "voltageC_v": 229.8,
                "relay_k1_v": 11.9,
                "relay_k2_v": 11.8,
                "pcba_temp_c": 31.2,
                "handle_temp_c": 24.5,
                "mcu_temp_c": 38.7,
                "uptime_s": 86400,
                "input_thermopile_uv": -150,
                "prox_v": 1.6,
                "pilot_high_v": 6.0,
                "pilot_low_v": -11.9,
                "session_energy_wh": 11000.5,
                "config_status": 5,
                "evse_state": 11,
                "current_alerts": [],
                "evse_not_ready_reasons": [],
            }
        ),
        lifetime_data=Lifetime(
            {
                "contactor_cycles": 120,
                "contactor_cycles_loaded": 2,
                "alert_count": 15,
                "thermal_foldbacks": 0,
                "avg_startup_temp": 21.5,
                "charge_starts": 120,
                "energy_wh": 1500000,
                "connector_cycles": 80,
                "uptime_s": 31536000,
                "charging_time_s": 864000,
            }
        ),
        wifi_status_data=WifiStatus(
            {
                "wifi_ssid": "SG9tZU5ldHdvcms=",
                "wifi_signal_strength": 65,
                "wifi_rssi": -55,
                "wifi_snr": 30,
                "wifi_connected": True,
                "wifi_infra_ip": "192.168.1.50",
                "internet": True,
                "wifi_mac": "98:ED:5C:12:34:56",
            }
        ),
    )

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
