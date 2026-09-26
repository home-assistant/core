"""Test the Tesla Fleet sensor platform."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.tesla_fleet.const import ENERGY_HISTORY_FIELDS
from homeassistant.components.tesla_fleet.coordinator import (
    ENERGY_HISTORY_INTERVAL,
    VEHICLE_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import (
    ENERGY_HISTORY,
    ENERGY_HISTORY_OVERNIGHT,
    VEHICLE_DATA,
    VEHICLE_DATA_ALT,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the sensor entities are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)

    # Coordinator refresh
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert_entities_alt(hass, normal_config_entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("entity_id", "initial", "restored"),
    [
        ("sensor.test_battery_level", "77", "77"),
        ("sensor.test_outside_temperature", "30", "30"),
        ("sensor.test_time_to_arrival", "2024-01-01T00:00:06+00:00", STATE_UNAVAILABLE),
    ],
)
async def test_sensors_restore(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    entity_id: str,
    initial: str,
    restored: str,
) -> None:
    """Test if the sensor should restore it's state or not when vehicle is offline."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    assert hass.states.get(entity_id).state == initial

    mock_vehicle_data.side_effect = VehicleOffline

    with patch("homeassistant.components.tesla_fleet.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_reload(normal_config_entry.entry_id)

    assert hass.states.get(entity_id).state == restored


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_charge_energy_reset(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test reset detection for polling charge energy sensors."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Set initial charge_energy_added to 10
    initial_data = deepcopy(VEHICLE_DATA)
    initial_data["response"]["charge_state"]["charge_energy_added"] = 10.0
    mock_vehicle_data.return_value = initial_data
    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])
    entity_id = "sensor.test_charge_energy_added"

    state = hass.states.get(entity_id)
    assert state.state == "10.0"
    assert state.attributes.get("last_reset") is None

    # Small correction should NOT trigger reset
    correction_data = deepcopy(VEHICLE_DATA)
    correction_data["response"]["charge_state"]["charge_energy_added"] = 9.5
    mock_vehicle_data.return_value = correction_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "9.5"
    assert state.attributes.get("last_reset") is None

    # Drop to 0 should trigger reset
    freezer.move_to("2024-01-01 01:00:00+00:00")
    reset_data = deepcopy(VEHICLE_DATA)
    reset_data["response"]["charge_state"]["charge_energy_added"] = 0
    mock_vehicle_data.return_value = reset_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "0"
    assert state.attributes.get("last_reset") is not None
    last_reset = state.attributes["last_reset"]

    # Additional 0 updates should not move last_reset forward
    freezer.move_to("2024-01-01 01:30:00+00:00")
    mock_vehicle_data.return_value = reset_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "0"
    assert state.attributes["last_reset"] == last_reset


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_charge_energy_restore_last_reset(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test that last_reset is restored after reload."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Set initial charge_energy_added to 10
    initial_data = deepcopy(VEHICLE_DATA)
    initial_data["response"]["charge_state"]["charge_energy_added"] = 10.0
    mock_vehicle_data.return_value = initial_data
    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])
    entity_id = "sensor.test_charge_energy_added"

    # Trigger reset
    freezer.move_to("2024-01-01 01:00:00+00:00")
    reset_data = deepcopy(VEHICLE_DATA)
    reset_data["response"]["charge_state"]["charge_energy_added"] = 0
    mock_vehicle_data.return_value = reset_data
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    last_reset = state.attributes["last_reset"]
    assert last_reset is not None

    # Reload the entry
    mock_vehicle_data.return_value = VEHICLE_DATA
    with patch("homeassistant.components.tesla_fleet.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_reload(normal_config_entry.entry_id)

    # last_reset should be restored
    state = hass.states.get(entity_id)
    assert state.attributes["last_reset"] == last_reset


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("history", "last_reset"),
    [
        pytest.param(ENERGY_HISTORY, "2023-06-01T01:00:00-07:00", id="mid_period"),
        pytest.param(
            ENERGY_HISTORY_OVERNIGHT, "2026-09-12T00:00:00+01:00", id="local_midnight"
        ),
    ],
)
async def test_energy_history_last_reset(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    history: dict[str, Any],
    last_reset: str,
) -> None:
    """Test that energy history sensors have last_reset from period start."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    mock_energy_history.return_value = history

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    entity_id = "sensor.energy_site_battery_discharged"

    # Trigger coordinator refresh to populate data
    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes.get("last_reset") == last_reset


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        pytest.param("sensor.energy_site_solar_generated", "0.0", id="solar_generated"),
        pytest.param("sensor.energy_site_grid_exported", "0.0", id="grid_exported"),
        pytest.param(
            "sensor.energy_site_battery_discharged", "0.0", id="battery_discharged"
        ),
        pytest.param("sensor.energy_site_battery_charged", "4.1", id="battery_charged"),
        pytest.param("sensor.energy_site_home_usage", "1.0", id="home_usage"),
        pytest.param("sensor.energy_site_grid_imported", "5.1", id="grid_imported"),
    ],
)
async def test_energy_history_omitted_fields_are_zero(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test fields Tesla omits from every period report zero, not unknown."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    mock_energy_history.return_value = ENERGY_HISTORY_OVERNIGHT

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_history_invalid_first_period(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
) -> None:
    """Test that malformed first-period history data makes sensors unavailable."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    entity_id = "sensor.energy_site_battery_discharged"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"

    invalid_history = deepcopy(ENERGY_HISTORY)
    invalid_history["response"]["time_series"][0].pop("timestamp")
    mock_energy_history.return_value = invalid_history

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


def _history_with_values(values: dict[str, Any]) -> dict[str, Any]:
    """Return overnight history with only the given fields in every period."""
    history = deepcopy(ENERGY_HISTORY_OVERNIGHT)
    history["response"]["time_series"] = [
        {"timestamp": period["timestamp"], **values}
        for period in history["response"]["time_series"]
    ]
    return history


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "history",
    [
        pytest.param(_history_with_values({}), id="no_fields"),
        pytest.param(
            _history_with_values(
                {"total_home_usage": True, "grid_energy_imported": "1250"}
            ),
            id="only_non_numeric",
        ),
    ],
)
async def test_energy_history_no_readings_are_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    history: dict[str, Any],
) -> None:
    """Test history without any numeric reading reports unknown, not zero."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    mock_energy_history.return_value = history

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, normal_config_entry.entry_id
        )
        if entry.unique_id.rsplit("-", 1)[-1] in ENERGY_HISTORY_FIELDS
    ]
    assert len(entity_ids) == len(ENERGY_HISTORY_FIELDS)
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        pytest.param("sensor.energy_site_home_usage", "0.51", id="partly_non_numeric"),
        pytest.param("sensor.energy_site_solar_generated", "0.0", id="all_non_numeric"),
        pytest.param("sensor.energy_site_grid_imported", "5.1", id="numeric"),
    ],
)
async def test_energy_history_non_numeric_values_skipped(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test non-numeric history values are skipped rather than summed."""

    history = deepcopy(ENERGY_HISTORY_OVERNIGHT)
    time_series = history["response"]["time_series"]
    time_series[0]["total_home_usage"] = "250"
    time_series[1]["total_home_usage"] = True
    for period in time_series:
        period["total_solar_generation"] = None

    freezer.move_to("2024-01-01 00:00:00+00:00")
    mock_energy_history.return_value = history

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
