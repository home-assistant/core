"""Tests for the APsystems Local API integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

LAKE6_IP = "1.2.3.4"
LAKE6_DEV_ID = "LAKE6_SERIAL_NUMBER"

LAKE6_DEVICES_PAYLOAD: dict[str, object] = {
    "dev_id": LAKE6_DEV_ID,
    "type": "Ema",
    "dev_ver": "V1.5.2",
    "bat_cap": "5.0",
    # The device sends rssi as a JSON number, not as a string.
    "rssi": -52,
}

LAKE6_ENERGIES_PAYLOAD: dict[str, object] = {
    "bat_soc": "30.0",
    "bat_temp": "25.0",
    "dev_temp": "31.0",
    "bat_impE": "57.28800",
    "bat_expE": "12.50000",
    "ongrid_expE": "100.10000",
    "ongrid_impE": "200.20000",
    "offgrid_expE": "0.00000",
    "offgrid_impE": "0.00000",
    "bat_power": "-486",
    "ongrid_power": "1200",
    "offgrid_power": "0",
    "bat_status": "2",
}

LAKE6_ALARMS_PAYLOAD: dict[str, object] = {
    "bat_overtemp": "1",
    "bat_undertemp": "0",
    "bat_comm_err": "0",
    "bat_overvolt": "0",
    "bat_undervolt": "0",
    "bat_overcur": "0",
    "bat_ie": "0",
    "dev_temp": "0",
    "dev_sys_err": "0",
    "bat_shutdown": "0",
    "grid_anomaly": "0",
    "offgrid_overcur": "0",
    "offgrid_shortcir": "0",
    "bat_cal": "0",
}

LAKE6_MODES_PAYLOAD: dict[str, object] = {
    # Time-of-use, the only mode in which time_cfg has any effect.
    "mode": "3",
    "eco": "0",
    "dod": "15",
    "time_cfg": [
        {
            "E": "1",
            "W": [1, 2, 3, 4, 5],
            "TM": [
                {
                    "T": "09000910",
                    "F": "2",
                    "FI": {"P": "200", "GD": 1},
                }
            ],
        },
        {"E": "1", "W": [6, 7], "TM": [{"T": "10001010", "F": "3", "FI": {}}]},
    ],
}

LAKE6_IDLE_PAYLOAD: dict[str, object] = {"mode": "0", "MI1": {}}

LAKE6_ACTIVE_PAYLOAD: dict[str, object] = {
    "mode": "1",
    "MI1": {
        "time": ["2026112510000020261125103000"],
        "power": ["500"],
    },
}


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
