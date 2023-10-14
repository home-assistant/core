"""Tests for the Withings component."""
from datetime import timedelta
from unittest.mock import AsyncMock

from aiowithings import MeasurementGroup
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.withings.const import DOMAIN
from homeassistant.components.withings.sensor import MEASUREMENT_SENSORS, SLEEP_SENSORS
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import USER_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_array_fixture,
    load_json_object_fixture,
)


async def async_get_entity_id(
    hass: HomeAssistant,
    key: str,
    user_id: int,
    platform: str,
) -> str | None:
    """Get an entity id for a user's attribute."""
    entity_registry = er.async_get(hass)
    unique_id = f"withings_{user_id}_{key}"

    return entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, polling_config_entry)

    for sensor in list(MEASUREMENT_SENSORS.values()) + SLEEP_SENSORS:
        entity_id = await async_get_entity_id(hass, sensor.key, USER_ID, SENSOR_DOMAIN)
        assert hass.states.get(entity_id) == snapshot


async def test_update_failed(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""
    await setup_integration(hass, polling_config_entry, False)

    withings.get_measurement_since.side_effect = Exception
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.henk_weight")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_update_updates_incrementally(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fetching new data updates since the last valid update."""
    await setup_integration(hass, polling_config_entry, False)

    async def _skip_10_minutes() -> None:
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    meas_json = load_json_array_fixture("withings/get_meas_1.json")
    measurement_groups = [
        MeasurementGroup.from_api(measurement) for measurement in meas_json
    ]

    assert withings.get_measurement_since.call_args_list == []
    await _skip_10_minutes()
    assert (
        str(withings.get_measurement_since.call_args_list[0].args[0])
        == "2019-08-01 12:00:00+00:00"
    )

    withings.get_measurement_since.return_value = measurement_groups
    await _skip_10_minutes()
    assert (
        str(withings.get_measurement_since.call_args_list[1].args[0])
        == "2019-08-01 12:00:00+00:00"
    )

    await _skip_10_minutes()
    assert (
        str(withings.get_measurement_since.call_args_list[2].args[0])
        == "2021-04-16 20:30:55+00:00"
    )

    state = hass.states.get("sensor.henk_weight")
    assert state is not None
    assert state.state == "71"
    assert len(withings.get_measurement_in_period.call_args_list) == 1


async def test_update_new_sensor_creates_new_sensor(
    hass: HomeAssistant,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fetching a new data point will add a new sensor."""
    meas_json = load_json_array_fixture("withings/get_meas_1.json")
    measurement_groups = [
        MeasurementGroup.from_api(measurement) for measurement in meas_json
    ]
    withings.get_measurement_in_period.return_value = measurement_groups
    await setup_integration(hass, polling_config_entry, False)

    async def _skip_10_minutes() -> None:
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.henk_fat_mass") is None

    meas_json = load_json_object_fixture("withings/get_meas.json")
    measurement_groups = [
        MeasurementGroup.from_api(measurement)
        for measurement in meas_json["measuregrps"]
    ]
    withings.get_measurement_in_period.return_value = measurement_groups
    await _skip_10_minutes()

    assert hass.states.get("sensor.henk_fat_mass") is not None
