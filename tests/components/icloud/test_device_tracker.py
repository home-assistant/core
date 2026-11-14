"""Tests for the iCloud device tracker platform."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
import math

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.typing import MagicMock

from homeassistant.components.icloud.const import (
    ATTR_ACCOUNT_FETCH_INTERVAL,
    ATTR_BATTERY,
    ATTR_BATTERY_STATUS,
    ATTR_DEVICE_STATUS,
    DOMAIN,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DEVICE, LOCATION, MAX_INTERVAL

ENTITY_ID = "device_tracker.iphone"
TRACKER_UNIQUE_ID = "device1"


async def test_tracker_keeps_the_device_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    icloud_service: MagicMock,
    setup_entry: Callable[[Platform], Awaitable[None]],
) -> None:
    """The tracker exposes the device attributes it carried before."""
    icloud_service.devices.add({**DEVICE, "location": LOCATION})

    await setup_entry(Platform.DEVICE_TRACKER)

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, TRACKER_UNIQUE_ID
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_ACCOUNT_FETCH_INTERVAL] == MAX_INTERVAL
    assert state.attributes[ATTR_BATTERY] == 80
    assert state.attributes[ATTR_BATTERY_STATUS] == "NotCharging"
    assert state.attributes[ATTR_DEVICE_STATUS] == "online"


def location(
    *, is_old: bool, age: timedelta, latitude: float = 1.0, longitude: float = 2.0
) -> dict:
    """Return a location fix of a given age, as iCloud reports it."""
    fixed_at = dt_util.utcnow() - age
    return {
        "latitude": latitude,
        "longitude": longitude,
        "horizontalAccuracy": 10,
        "isOld": is_old,
        "timeStamp": fixed_at.timestamp() * 1000,
    }


@pytest.fixture(name="status")
def mock_status(icloud_service: MagicMock) -> dict:
    """Add a device with a fresh location and return its status."""
    status = {**DEVICE, "location": location(is_old=False, age=timedelta(0))}
    icloud_service.devices.add(status)
    return status


async def next_fetch(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the account poll iCloud again."""
    freezer.tick(timedelta(minutes=MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("status")
async def test_location_reported(
    hass: HomeAssistant, setup_entry: Callable[[Platform], Awaitable[None]]
) -> None:
    """Test that a fresh fix is reported."""
    await setup_entry(Platform.DEVICE_TRACKER)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 1.0
    assert state.attributes[ATTR_LONGITUDE] == 2.0


async def test_devices_appearing_in_one_poll_all_get_their_trackers(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that every device that turns up in one poll gets its tracker.

    The platforms iterate the account's devices on the event loop while the
    poll adds them from the executor, so they are told once the poll has
    finished adding devices, and what they build then has to cover all of them.
    """
    await setup_entry(Platform.DEVICE_TRACKER)

    status["location"] = location(is_old=True, age=timedelta(minutes=MAX_INTERVAL * 3))
    await next_fetch(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    # The first device regains its location, and another one appears after it.
    status["location"] = location(is_old=False, age=timedelta(0))
    icloud_service.devices.add(
        {**status, "id": "device2", "name": "iPad", "deviceDisplayName": "iPad"}
    )
    await next_fetch(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_LATITUDE] == 1.0
    assert hass.states.get("device_tracker.ipad").attributes[ATTR_LATITUDE] == 1.0


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        pytest.param(0.0, 4.0, id="equator"),
        pytest.param(3.0, 0.0, id="prime_meridian"),
        pytest.param(0.0, 0.0, id="both"),
    ],
)
async def test_a_coordinate_of_zero_is_a_valid_location(
    hass: HomeAssistant,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
    latitude: float,
    longitude: float,
) -> None:
    """Test that a fix on the equator or the prime meridian is accepted.

    Zero is a coordinate, not a missing one, so only a missing coordinate may
    be treated as no location.
    """
    await setup_entry(Platform.DEVICE_TRACKER)

    status["location"] = location(
        is_old=False, age=timedelta(0), latitude=latitude, longitude=longitude
    )
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == latitude
    assert state.attributes[ATTR_LONGITUDE] == longitude


async def test_stale_location_cleared(
    hass: HomeAssistant,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a cached fix older than a polling cycle is discarded."""
    await setup_entry(Platform.DEVICE_TRACKER)
    assert ATTR_LATITUDE in hass.states.get(ENTITY_ID).attributes

    # iCloud keeps serving the same fix, now a cached one and older than a
    # full polling cycle: the device has moved on without telling us.
    status["location"] = location(is_old=True, age=timedelta(minutes=MAX_INTERVAL * 3))
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert ATTR_LATITUDE not in state.attributes
    # No coordinates and no zone, so the tracker reports that it does not
    # know where the device is rather than claiming it is away.
    assert state.state == STATE_UNKNOWN


async def test_recent_cached_location_kept(
    hass: HomeAssistant,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a cached but recent fix is kept.

    A device that was only briefly unreachable is reported the same way as one
    that has moved away, so the flag alone must not discard a location.
    """
    await setup_entry(Platform.DEVICE_TRACKER)

    status["location"] = location(is_old=True, age=timedelta(seconds=30))
    await next_fetch(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_LATITUDE] == 1.0


async def test_old_uncached_location_kept(
    hass: HomeAssistant,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an old fix iCloud still considers current is kept.

    A device that is sitting still reports an old timestamp indefinitely, so
    age alone must not be enough to discard a location either.
    """
    await setup_entry(Platform.DEVICE_TRACKER)

    status["location"] = location(is_old=False, age=timedelta(minutes=MAX_INTERVAL * 3))
    await next_fetch(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_LATITUDE] == 1.0


async def test_cached_location_without_a_timestamp_is_kept(
    hass: HomeAssistant,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a cached fix without a timestamp is kept.

    Age is half of what makes a fix stale, so with no timestamp to read there
    is nothing to judge it by. Discarding it on the flag alone would throw
    away the only location such a device reports.
    """
    await setup_entry(Platform.DEVICE_TRACKER)

    fix = location(
        is_old=True,
        age=timedelta(minutes=MAX_INTERVAL * 3),
        latitude=3.0,
        longitude=4.0,
    )
    del fix["timeStamp"]
    status["location"] = fix
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 3.0
    assert state.attributes[ATTR_LONGITUDE] == 4.0


async def test_tracker_is_created_once_a_stale_first_fix_is_replaced(
    hass: HomeAssistant,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device first seen with a stale fix gets its tracker later.

    The tracker platform skips a device without a location, so the entity can
    only appear when a fresh fix arrives and announces the device.
    """
    status["location"] = location(is_old=True, age=timedelta(minutes=MAX_INTERVAL * 3))
    await setup_entry(Platform.DEVICE_TRACKER)
    assert hass.states.get(ENTITY_ID) is None

    status["location"] = location(is_old=False, age=timedelta(seconds=30))
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 1.0
    assert state.attributes[ATTR_LONGITUDE] == 2.0


@pytest.mark.parametrize(
    "timestamp",
    [
        pytest.param(None, id="null"),
        pytest.param("not-a-number", id="not_a_number"),
        pytest.param(True, id="bool"),
        pytest.param(math.nan, id="nan"),
        pytest.param(math.inf, id="infinity"),
        pytest.param(1e30, id="out_of_range"),
    ],
)
async def test_cached_location_with_an_unusable_timestamp_is_kept(
    hass: HomeAssistant,
    status: dict,
    setup_entry: Callable[[Platform], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
    timestamp: object,
) -> None:
    """Test that a timestamp that is there but cannot be read does not end the poll.

    iCloud has no reason to send anything but a number, but arithmetic on
    anything else raises inside the poll. A fix that cannot be dated is kept,
    the same as one that carries no timestamp at all.
    """
    await setup_entry(Platform.DEVICE_TRACKER)

    status["location"] = location(
        is_old=True,
        age=timedelta(minutes=MAX_INTERVAL * 3),
        latitude=3.0,
        longitude=4.0,
    ) | {"timeStamp": timestamp}
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 3.0
    assert state.attributes[ATTR_LONGITUDE] == 4.0
