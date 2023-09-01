"""The tests for Electric Kiwi sensors."""


from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.electric_kiwi import (
    DOMAIN,
    ElectricKiwiHOPDataCoordinator,
)
from homeassistant.components.electric_kiwi.const import ATTRIBUTION
from homeassistant.components.electric_kiwi.sensor import _check_and_move_time
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
import homeassistant.util.dt as dt_util

from .conftest import TIMEZONE

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
    ek_api: AsyncMock,
    entity_registry: EntityRegistry,
    sensor: str,
    sensor_state: str,
) -> None:
    """Test HOP sensors for the Electric Kiwi integration.

    This time (note no day is given, it's only a time) is fed from the Electric Kiwi API.
    if the API returns 4:00 PM, the sensor state should be set to today at 4pm or if now is past 4pm, then tomorrow at 4pm

    """

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        return_value=AsyncMock(),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert entries[0].state is ConfigEntryState.LOADED

        hop_coordinator: ElectricKiwiHOPDataCoordinator = hass.data[DOMAIN][
            config_entry.entry_id
        ]
        assert hop_coordinator
        entity = entity_registry.async_get(sensor)
        assert entity

        state = hass.states.get(sensor)
        assert state
        value = _check_and_move_time(hop_coordinator.data, sensor_state)

        value = value.astimezone(UTC)
        assert state.state == value.isoformat(timespec="seconds")
        assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP


async def test_check_and_move_time(ek_api: AsyncMock) -> None:
    """Test correct time is returned for the hop time depending on time of day."""
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
