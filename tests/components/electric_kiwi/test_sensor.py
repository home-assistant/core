"""The tests for Electric Kiwi sensors."""


from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

from freezegun import freeze_time
import pytest

from homeassistant.components.electric_kiwi.const import ATTRIBUTION
from homeassistant.components.electric_kiwi.sensor import _check_and_move_time
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
import homeassistant.util.dt as dt_util

from .conftest import TIMEZONE, ComponentSetup, YieldFixture

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("sensor", "sensor_state"),
    [
        ("sensor.hour_of_free_power_start", "4:00 PM"),
        ("sensor.hour_of_free_power_end", "5:00 PM"),
    ],
)
async def test_hop_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ek_api: YieldFixture,
    ek_auth: YieldFixture,
    entity_registry: EntityRegistry,
    component_setup: ComponentSetup,
    sensor: str,
    sensor_state: str,
) -> None:
    """Test HOP sensors for the Electric Kiwi integration.

    This time (note no day is given, it's only a time) is fed
    from the Electric Kiwi API. if the API returns 4:00 PM, the
    sensor state should be set to today at 4pm or if now is past 4pm,
    then tomorrow at 4pm.
    """
    assert await component_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    entity = entity_registry.async_get(sensor)
    assert entity

    state = hass.states.get(sensor)
    assert state

    api = ek_api(Mock())
    hop_data = await api.get_hop()

    value = _check_and_move_time(hop_data, sensor_state)

    value = value.astimezone(UTC)
    assert state.state == value.isoformat(timespec="seconds")
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP


@pytest.mark.parametrize(
    ("sensor", "sensor_state", "device_class", "state_class"),
    [
        (
            "sensor.total_running_balance",
            "184.09",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
        ),
        (
            "sensor.total_current_balance",
            "-102.22",
            SensorDeviceClass.MONETARY,
            SensorStateClass.TOTAL,
        ),
        (
            "sensor.next_billing_date",
            "2020-11-03T00:00:00",
            SensorDeviceClass.DATE,
            None,
        ),
        ("sensor.hour_of_power_savings", "3.5", None, SensorStateClass.MEASUREMENT),
    ],
)
async def test_account_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ek_api: YieldFixture,
    ek_auth: YieldFixture,
    entity_registry: EntityRegistry,
    component_setup: ComponentSetup,
    sensor: str,
    sensor_state: str,
    device_class: str,
    state_class: str,
) -> None:
    """Test Account sensors for the Electric Kiwi integration."""

    assert await component_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    entity = entity_registry.async_get(sensor)
    assert entity

    state = hass.states.get(sensor)
    assert state
    assert state.state == sensor_state
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class
    assert state.attributes.get(ATTR_STATE_CLASS) == state_class


async def test_check_and_move_time(ek_api: AsyncMock) -> None:
    """Test correct time is returned depending on time of day."""
    hop = await ek_api(Mock()).get_hop()

    test_time = datetime(2023, 6, 21, 18, 0, 0, tzinfo=TIMEZONE)
    dt_util.set_default_time_zone(TIMEZONE)

    with freeze_time(test_time):
        value = _check_and_move_time(hop, "4:00 PM")
        assert str(value) == "2023-06-22 16:00:00+12:00"

    test_time = test_time.replace(hour=10)

    with freeze_time(test_time):
        value = _check_and_move_time(hop, "4:00 PM")
        assert str(value) == "2023-06-21 16:00:00+12:00"
