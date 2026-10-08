"""Tests for the OpenEVSE integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from openevsehttp.exceptions import (
    AuthenticationError,
    MissingSerial,
    UnsupportedFeature,
)

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.components.openevse.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_entry_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test setup entry raises ConfigEntryNotReady on timeout."""
    mock_charger.test_and_get.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test setup entry triggers reauth on authentication error."""
    mock_charger.test_and_get.side_effect = AuthenticationError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_coordinator_update_auth_error_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test coordinator update triggers reauth on authentication error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_charger.update.side_effect = AuthenticationError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test unload entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_missing_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test setup entry succeeds when serial number is missing."""
    mock_charger.test_and_get.side_effect = MissingSerial

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_sensor_state_change_pushes_data(
    hass: HomeAssistant,
    mock_charger: MagicMock,
) -> None:
    """Test state changes to configured sensor entities push data to OpenEVSE."""
    mock_charger.self_production = AsyncMock()
    mock_charger.grid_voltage = AsyncMock()
    mock_charger.set_shaper_live_pwr = AsyncMock()
    mock_charger.soc = AsyncMock()
    mock_charger.home_battery = AsyncMock()

    config_entry = MockConfigEntry(
        title="OpenEVSE",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        entry_id="FAKE",
        unique_id="deadbeeffeed",
        options={
            "grid": "sensor.grid_power",
            "solar": "sensor.solar_power",
            "voltage": "sensor.grid_voltage",
            "shaper": "sensor.shaper_power",
            "vehicle_soc": "sensor.car_battery",
            "vehicle_range": "sensor.car_range",
            "vehicle_eta": "sensor.car_eta",
            "home_battery_soc": "sensor.home_battery_soc",
            "home_battery_power": "sensor.home_battery_power",
            "invert_grid": True,
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Grid update (with kW conversion and invert)
    hass.states.async_set("sensor.grid_power", "2.5", {"unit_of_measurement": "kW"})
    await hass.async_block_till_done()
    mock_charger.self_production.assert_called_with(grid=2500, solar=None, invert=True)

    # Solar update
    hass.states.async_set("sensor.solar_power", "1800", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    mock_charger.self_production.assert_called_with(grid=None, solar=1800, invert=False)

    # Voltage update
    hass.states.async_set("sensor.grid_voltage", "240.4")
    await hass.async_block_till_done()
    mock_charger.grid_voltage.assert_called_with(voltage=240)

    # Shaper power update
    hass.states.async_set("sensor.shaper_power", "5000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    mock_charger.set_shaper_live_pwr.assert_called_with(power=5000)

    # Vehicle SoC update
    hass.states.async_set("sensor.car_battery", "80")
    await hass.async_block_till_done()
    mock_charger.soc.assert_called_with(
        battery_level=80, battery_range=None, time_to_full=None
    )

    # Vehicle range update (now includes previous or current SoC if set)
    hass.states.async_set("sensor.car_range", "220")
    await hass.async_block_till_done()
    mock_charger.soc.assert_called_with(
        battery_level=80, battery_range=220, time_to_full=None
    )

    # Vehicle ETA update (now includes all three)
    hass.states.async_set("sensor.car_eta", "3600")
    await hass.async_block_till_done()
    mock_charger.soc.assert_called_with(
        battery_level=80, battery_range=220, time_to_full=3600
    )

    # Vehicle ETA update with datetime sensor (converts to remaining seconds)
    eta_dt = dt_util.utcnow() + timedelta(seconds=1800)
    hass.states.async_set("sensor.car_eta", eta_dt.isoformat())
    await hass.async_block_till_done()
    assert mock_charger.soc.call_args.kwargs["time_to_full"] in (1799, 1800, 1801)

    # Vehicle ETA update with duration unit sensor (converts to seconds)
    hass.states.async_set("sensor.car_eta", "30", {"unit_of_measurement": "min"})
    await hass.async_block_till_done()
    assert mock_charger.soc.call_args.kwargs["time_to_full"] == 1800

    # Home battery SoC update
    hass.states.async_set("sensor.home_battery_soc", "95")
    await hass.async_block_till_done()
    mock_charger.home_battery.assert_called_with(soc=95, power=None)

    # Home battery power update (now includes SoC as well)
    hass.states.async_set(
        "sensor.home_battery_power", "3200", {"unit_of_measurement": "W"}
    )
    await hass.async_block_till_done()
    mock_charger.home_battery.assert_called_with(soc=95, power=3200)

    # Invalid / non-numeric states should not crash
    hass.states.async_set("sensor.grid_power", "unknown")
    hass.states.async_set("sensor.grid_voltage", "invalid")
    await hass.async_block_till_done()

    # UnsupportedFeature and TimeoutError should be caught gracefully
    mock_charger.soc.side_effect = UnsupportedFeature
    hass.states.async_set("sensor.car_battery", "85")
    await hass.async_block_till_done()

    mock_charger.self_production.side_effect = TimeoutError
    hass.states.async_set("sensor.grid_power", "3000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
