"""Tests for the OpenEVSE integration."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ServerTimeoutError
from freezegun.api import FrozenDateTimeFactory
from openevsehttp.exceptions import (
    AuthenticationError,
    MissingSerial,
    ParseJSONError,
    UnsupportedFeature,
)

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.components.openevse.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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
    freezer: FrozenDateTimeFactory,
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
    push_event = asyncio.Event()

    def _sync_mock(mock_method: AsyncMock) -> None:
        orig = mock_method.side_effect

        async def _wrapper(*args, **kwargs):
            try:
                if isinstance(orig, type) and issubclass(orig, BaseException):
                    raise orig
                if isinstance(orig, BaseException):
                    raise orig
                if callable(orig):
                    return await orig(*args, **kwargs)
                return None
            finally:
                push_event.set()

        mock_method.side_effect = _wrapper

    for method in (
        mock_charger.self_production,
        mock_charger.grid_voltage,
        mock_charger.set_shaper_live_pwr,
        mock_charger.soc,
        mock_charger.home_battery,
    ):
        _sync_mock(method)

    async def _wait_for_push() -> None:
        async with asyncio.timeout(1):
            await push_event.wait()
        push_event.clear()

    freezer.move_to("2026-10-14 12:00:00+00:00")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    hass.states.async_set("sensor.grid_power", "2.5", {"unit_of_measurement": "kW"})
    await _wait_for_push()
    mock_charger.self_production.assert_called_with(grid=2500, solar=None, invert=True)

    hass.states.async_set("sensor.solar_power", "1800", {"unit_of_measurement": "W"})
    await _wait_for_push()
    mock_charger.self_production.assert_called_with(grid=None, solar=1800, invert=False)

    hass.states.async_set("sensor.grid_voltage", "240.4")
    await _wait_for_push()
    mock_charger.grid_voltage.assert_called_with(voltage=240)

    hass.states.async_set("sensor.grid_voltage", "0.24", {"unit_of_measurement": "kV"})
    await _wait_for_push()
    mock_charger.grid_voltage.assert_called_with(voltage=240)

    hass.states.async_set("sensor.shaper_power", "5000", {"unit_of_measurement": "W"})
    await _wait_for_push()
    mock_charger.set_shaper_live_pwr.assert_called_with(power=5000)

    hass.states.async_set("sensor.car_battery", "80")
    await _wait_for_push()
    mock_charger.soc.assert_called_with(
        battery_level=80, battery_range=None, time_to_full=None
    )

    hass.states.async_set("sensor.car_range", "220")
    await _wait_for_push()
    mock_charger.soc.assert_called_with(
        battery_level=80, battery_range=220, time_to_full=None
    )

    hass.states.async_set("sensor.car_range", "100", {"unit_of_measurement": "mi"})
    await _wait_for_push()
    mock_charger.soc.assert_called_with(
        battery_level=80, battery_range=161, time_to_full=None
    )

    hass.states.async_set("sensor.car_eta", "3600")
    await _wait_for_push()
    mock_charger.soc.assert_called_with(
        battery_level=80, battery_range=161, time_to_full=3600
    )

    eta_dt = dt_util.utcnow() + timedelta(seconds=1800)
    hass.states.async_set("sensor.car_eta", eta_dt.isoformat())
    await _wait_for_push()
    assert mock_charger.soc.call_args.kwargs["time_to_full"] == 1800

    hass.states.async_set("sensor.car_eta", "30", {"unit_of_measurement": "min"})
    await _wait_for_push()
    assert mock_charger.soc.call_args.kwargs["time_to_full"] == 1800

    hass.states.async_set("sensor.home_battery_soc", "95")
    await _wait_for_push()
    mock_charger.home_battery.assert_called_with(soc=95, power=None)

    hass.states.async_set(
        "sensor.home_battery_power", "3200", {"unit_of_measurement": "W"}
    )
    await _wait_for_push()
    mock_charger.home_battery.assert_called_with(soc=95, power=3200)

    mock_charger.grid_voltage.reset_mock()
    hass.states.async_set("sensor.grid_power", "unknown")
    hass.states.async_set("sensor.grid_voltage", "invalid")
    await hass.async_block_till_done()
    mock_charger.grid_voltage.assert_not_called()

    mock_charger.soc.side_effect = UnsupportedFeature
    _sync_mock(mock_charger.soc)
    hass.states.async_set("sensor.car_battery", "85")
    await _wait_for_push()

    mock_charger.self_production.side_effect = TimeoutError
    _sync_mock(mock_charger.self_production)
    hass.states.async_set("sensor.grid_power", "3000", {"unit_of_measurement": "W"})
    await _wait_for_push()

    mock_charger.self_production.side_effect = ServerTimeoutError
    _sync_mock(mock_charger.self_production)
    hass.states.async_set("sensor.grid_power", "3100", {"unit_of_measurement": "W"})
    await _wait_for_push()

    mock_charger.self_production.side_effect = ParseJSONError
    _sync_mock(mock_charger.self_production)
    hass.states.async_set("sensor.grid_power", "3200", {"unit_of_measurement": "W"})
    await _wait_for_push()

    mock_charger.self_production.side_effect = ValueError("Invalid value")
    _sync_mock(mock_charger.self_production)
    hass.states.async_set("sensor.grid_power", "3300", {"unit_of_measurement": "W"})
    await _wait_for_push()

    mock_charger.self_production.side_effect = AuthenticationError
    _sync_mock(mock_charger.self_production)
    hass.states.async_set("sensor.grid_power", "3400", {"unit_of_measurement": "W"})
    await _wait_for_push()
    await hass.async_block_till_done()
    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_sensor_startup_replay_and_coalescing(
    hass: HomeAssistant,
    mock_charger: MagicMock,
) -> None:
    """Test that existing sensor states are replayed on setup and multiple updates coalesce."""
    mock_charger.self_production = AsyncMock()
    mock_charger.grid_voltage = AsyncMock()
    mock_charger.set_shaper_live_pwr = AsyncMock()
    mock_charger.soc = AsyncMock()
    mock_charger.home_battery = AsyncMock()

    push_event = asyncio.Event()

    def _sync_mock(mock_method: AsyncMock) -> None:
        async def _wrapper(*args, **kwargs):
            push_event.set()

        mock_method.side_effect = _wrapper

    for method in (
        mock_charger.self_production,
        mock_charger.grid_voltage,
        mock_charger.set_shaper_live_pwr,
        mock_charger.soc,
        mock_charger.home_battery,
    ):
        _sync_mock(method)

    hass.states.async_set("sensor.car_battery", "75")
    hass.states.async_set("sensor.car_range", "150")

    config_entry = MockConfigEntry(
        title="OpenEVSE",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        entry_id="FAKE",
        unique_id="deadbeeffeed",
        options={
            "vehicle_soc": "sensor.car_battery",
            "vehicle_range": "sensor.car_range",
            "grid": "sensor.grid_power",
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async with asyncio.timeout(1):
        await push_event.wait()
    push_event.clear()

    mock_charger.soc.assert_called_with(
        battery_level=75, battery_range=150, time_to_full=None
    )

    # Trigger multiple rapid state updates before block_till_done to test coalescing
    mock_charger.self_production.reset_mock()
    hass.states.async_set("sensor.grid_power", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.grid_power", "2000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.grid_power", "3000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()

    async with asyncio.timeout(1):
        await push_event.wait()

    assert mock_charger.self_production.call_count == 1
    mock_charger.self_production.assert_called_once_with(
        grid=3000, solar=None, invert=False
    )


async def test_sensor_entity_registry_rename(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_charger: MagicMock,
) -> None:
    """Test that renaming a configured sensor in entity registry updates entry and reloads."""
    sensor_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "car_battery_unique_id",
        suggested_object_id="car_battery",
    )
    assert sensor_entry.entity_id == "sensor.car_battery"

    config_entry = MockConfigEntry(
        title="OpenEVSE",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        entry_id="FAKE",
        unique_id="deadbeeffeed",
        options={
            "vehicle_soc": "sensor.car_battery",
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Rename entity in entity registry
    entity_registry.async_update_entity(
        "sensor.car_battery",
        new_entity_id="sensor.my_new_car_battery",
    )
    await hass.async_block_till_done()

    assert config_entry.options["vehicle_soc"] == "sensor.my_new_car_battery"
