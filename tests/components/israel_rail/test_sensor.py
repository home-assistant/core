"""Tests for the israel_rail sensor."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.israel_rail.const import DEPARTURES_COUNT
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import goto_future, init_integration
from .conftest import TRAINS, get_time, get_train_route

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# A moment just before the first train in TRAINS departs (10:10 UTC), so the
# coordinator considers the head of the list as an upcoming departure.
BEFORE_FIRST_TRAIN = "2021-10-10T10:00:00+00:00"

EXPECTED_ENTITY_COUNT = DEPARTURES_COUNT * 5


@pytest.fixture(autouse=True)
def freeze_before_first_train(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze time before any train in TRAINS departs."""
    freezer.move_to(BEFORE_FIRST_TRAIN)
    return freezer


async def test_valid_config(
    hass: HomeAssistant,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_train(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure the train data is updated."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == EXPECTED_ENTITY_COUNT
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    expected_time = get_time(10, 10)
    assert departure_sensor.state == expected_time

    mock_israelrail.query.return_value = TRAINS[1:]
    freeze_before_first_train.move_to("2021-10-10T10:15:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == EXPECTED_ENTITY_COUNT
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    expected_time = get_time(10, 20)
    assert departure_sensor.state == expected_time


async def test_fail_query(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure the integration handles query failures."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == EXPECTED_ENTITY_COUNT
    mock_israelrail.query.side_effect = Exception("error")
    await goto_future(hass, freeze_before_first_train)
    assert len(hass.states.async_entity_ids()) == EXPECTED_ENTITY_COUNT
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    assert departure_sensor.state == STATE_UNAVAILABLE


async def test_no_departures(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling when there are no departures available."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == EXPECTED_ENTITY_COUNT

    # Simulate no departures (e.g., after-hours)
    mock_israelrail.query.return_value = []

    await goto_future(hass, freeze_before_first_train)

    # All sensors should still exist
    assert len(hass.states.async_entity_ids()) == EXPECTED_ENTITY_COUNT

    # Departure sensors should have unknown state (None)
    departure_sensor = hass.states.get("sensor.mock_title_departure")
    assert departure_sensor.state == STATE_UNKNOWN

    departure_sensor_1 = hass.states.get("sensor.mock_title_departure_1")
    assert departure_sensor_1.state == STATE_UNKNOWN

    departure_sensor_2 = hass.states.get("sensor.mock_title_departure_2")
    assert departure_sensor_2.state == STATE_UNKNOWN

    # Non-departure sensors (platform, trains, train_number) also access index 0
    # and should have unknown state when no departures available
    platform_sensor = hass.states.get("sensor.mock_title_platform")
    assert platform_sensor.state == STATE_UNKNOWN

    trains_sensor = hass.states.get("sensor.mock_title_trains")
    assert trains_sensor.state == STATE_UNKNOWN

    train_number_sensor = hass.states.get("sensor.mock_title_train_number")
    assert train_number_sensor.state == STATE_UNKNOWN

    departure_delay_sensor = hass.states.get("sensor.mock_title_departure_delay")
    assert departure_delay_sensor.state == STATE_UNKNOWN


async def test_departure_delay(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure departure_delay is exposed as a sensor."""
    await init_integration(hass, mock_config_entry)

    departure_delay_sensor = hass.states.get("sensor.mock_title_departure_delay")
    assert departure_delay_sensor is not None
    assert departure_delay_sensor.state == "0"

    mock_israelrail.query.return_value = [
        get_train_route(
            train_number="1234",
            departure_time=get_time(10, 10),
            arrival_time=get_time(10, 30),
            departure_delay=7,
        ),
        *TRAINS[1:],
    ]

    # Refresh while still before TRAINS[0] departs, so the delay-bearing
    # first route is treated as upcoming and not skipped.
    freeze_before_first_train.move_to("2021-10-10T10:05:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    departure_delay_sensor = hass.states.get("sensor.mock_title_departure_delay")
    assert departure_delay_sensor.state == "7"


async def test_skip_first_route_when_in_past(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When the first route already departed, sensors should reflect the next ones."""
    # Freeze "now" between TRAINS[0] (10:10) and TRAINS[1] (10:20) so the head
    # of the list is in the past. Coordinator should shift the window by 1.
    freeze_before_first_train.move_to("2021-10-10T10:15:00+00:00")

    await init_integration(hass, mock_config_entry)

    # The +0/+1/+2 departure sensors should now show TRAINS[1], TRAINS[2], TRAINS[3].
    assert hass.states.get("sensor.mock_title_departure").state == get_time(10, 20)
    assert hass.states.get("sensor.mock_title_departure_1").state == get_time(10, 30)
    assert hass.states.get("sensor.mock_title_departure_2").state == get_time(10, 40)
    # The per-index sensors should also follow the shifted window — index 0
    # now points at the second route in the API response, index 1 at the third, etc.
    assert hass.states.get("sensor.mock_title_train_number").state == "1235"
    assert hass.states.get("sensor.mock_title_train_number_1").state == "1236"
    assert hass.states.get("sensor.mock_title_train_number_2").state == "1237"


async def test_keep_first_route_when_upcoming(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When the first route is still upcoming, sensors should keep it."""
    # "now" sits well before TRAINS[0] (10:10), so no offset is applied.
    await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_departure").state == get_time(10, 10)
    assert hass.states.get("sensor.mock_title_departure_1").state == get_time(10, 20)
    assert hass.states.get("sensor.mock_title_departure_2").state == get_time(10, 30)
    assert hass.states.get("sensor.mock_title_train_number").state == "1234"


async def test_skip_first_route_with_fewer_results(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A short result list with a past head still yields entries from the tail."""
    # Only two routes; the first is already in the past so only one remains.
    mock_israelrail.query.return_value = [TRAINS[0], TRAINS[1]]
    freeze_before_first_train.move_to("2021-10-10T10:15:00+00:00")

    await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_departure").state == get_time(10, 20)
    # No second/third routes available after the shift.
    assert hass.states.get("sensor.mock_title_departure_1").state == STATE_UNKNOWN
    assert hass.states.get("sensor.mock_title_departure_2").state == STATE_UNKNOWN


async def test_skip_multiple_past_routes(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When several routes at the head have already departed, the window shifts past them all."""
    # Freeze "now" past TRAINS[0] (10:10) and TRAINS[1] (10:20) but before TRAINS[2] (10:30).
    freeze_before_first_train.move_to("2021-10-10T10:25:00+00:00")

    await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_departure").state == get_time(10, 30)
    assert hass.states.get("sensor.mock_title_departure_1").state == get_time(10, 40)
    assert hass.states.get("sensor.mock_title_departure_2").state == get_time(10, 50)
    assert hass.states.get("sensor.mock_title_train_number").state == "1236"


async def test_all_routes_in_past(
    hass: HomeAssistant,
    freeze_before_first_train: FrozenDateTimeFactory,
    mock_israelrail: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When every returned route has already departed, every departure sensor is unknown."""
    freeze_before_first_train.move_to("2021-10-10T11:00:00+00:00")

    await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_departure").state == STATE_UNKNOWN
    assert hass.states.get("sensor.mock_title_departure_1").state == STATE_UNKNOWN
    assert hass.states.get("sensor.mock_title_departure_2").state == STATE_UNKNOWN
