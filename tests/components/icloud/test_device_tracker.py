"""Tests for the iCloud device tracker."""

from datetime import timedelta
import math
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.icloud.const import DEFAULT_MAX_INTERVAL, DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import MOCK_CONFIG, USERNAME

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "device_tracker.iphone"


def location(*, is_old: bool, age: timedelta) -> dict:
    """Return a location fix of a given age, as iCloud reports it."""
    fixed_at = dt_util.utcnow() - age
    return {
        "latitude": 1.0,
        "longitude": 2.0,
        "horizontalAccuracy": 10,
        "isOld": is_old,
        "timeStamp": fixed_at.timestamp() * 1000,
    }


async def setup_account(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the iCloud integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def next_fetch(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the account poll iCloud again."""
    freezer.tick(timedelta(minutes=DEFAULT_MAX_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("locating_service")
async def test_location_reported(hass: HomeAssistant) -> None:
    """Test that a fresh fix is reported."""
    await setup_account(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 1.0
    assert state.attributes[ATTR_LONGITUDE] == 2.0


async def test_stale_location_cleared(
    hass: HomeAssistant,
    locating_service: tuple,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a cached fix older than a polling cycle is discarded."""
    _, status = locating_service
    await setup_account(hass)
    assert ATTR_LATITUDE in hass.states.get(ENTITY_ID).attributes

    # iCloud keeps serving the same fix, now a cached one and older than a
    # full polling cycle: the device has moved on without telling us.
    status["location"] = location(
        is_old=True, age=timedelta(minutes=DEFAULT_MAX_INTERVAL * 3)
    )
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert ATTR_LATITUDE not in state.attributes
    # No coordinates and no zone, so the tracker reports that it does not
    # know where the device is rather than claiming it is away.
    assert state.state == STATE_UNKNOWN


async def test_recent_cached_location_kept(
    hass: HomeAssistant,
    locating_service: tuple,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a cached but recent fix is kept.

    A device that was only briefly unreachable is reported the same way as one
    that has moved away, so the flag alone must not discard a location.
    """
    _, status = locating_service
    await setup_account(hass)

    status["location"] = location(is_old=True, age=timedelta(seconds=30))
    await next_fetch(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_LATITUDE] == 1.0


async def test_old_uncached_location_kept(
    hass: HomeAssistant,
    locating_service: tuple,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an old fix iCloud still considers current is kept.

    A device that is sitting still reports an old timestamp indefinitely, so
    age alone must not be enough to discard a location either.
    """
    _, status = locating_service
    await setup_account(hass)

    status["location"] = location(
        is_old=False, age=timedelta(minutes=DEFAULT_MAX_INTERVAL * 3)
    )
    await next_fetch(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_LATITUDE] == 1.0


async def test_cached_location_without_a_timestamp_is_kept(
    hass: HomeAssistant,
    locating_service: tuple,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a cached fix iCloud dates is kept when it dates nothing.

    Age is half of what makes a fix stale, so with no timestamp to read there
    is nothing to judge it by. Discarding it on the flag alone would throw
    away the only location such a device reports.
    """
    _, status = locating_service
    await setup_account(hass)

    fix = location(is_old=True, age=timedelta(minutes=DEFAULT_MAX_INTERVAL * 3))
    del fix["timeStamp"]
    status["location"] = fix
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 1.0
    assert state.attributes[ATTR_LONGITUDE] == 2.0


async def test_tracker_is_created_once_a_stale_first_fix_is_replaced(
    hass: HomeAssistant,
    locating_service: tuple,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device first seen with a stale fix gets its tracker later.

    The tracker platform skips a device without a location, so the entity can
    only appear when a fresh fix arrives and announces the device.
    """
    _, status = locating_service
    status["location"] = location(
        is_old=True, age=timedelta(minutes=DEFAULT_MAX_INTERVAL * 3)
    )
    await setup_account(hass)
    assert hass.states.get(ENTITY_ID) is None

    status["location"] = location(is_old=False, age=timedelta(seconds=30))
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 1.0
    assert state.attributes[ATTR_LONGITUDE] == 2.0


async def test_recovered_location_is_stored_before_it_is_announced(
    hass: HomeAssistant,
    locating_service: tuple,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the new-device signal is sent once the location can be read.

    The poll runs off the event loop and the signal is handled on it, so a
    listener that finds no location skips the device and is never told again.
    """
    _, status = locating_service
    await setup_account(hass)
    status["location"] = location(
        is_old=True, age=timedelta(minutes=DEFAULT_MAX_INTERVAL * 3)
    )
    await next_fetch(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    account = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    (device,) = account.devices.values()
    seen: list[object] = []

    def record(hass: HomeAssistant, signal: str, *args: object) -> None:
        if signal == account.signal_device_new:
            seen.append(device.location)

    status["location"] = location(is_old=False, age=timedelta(seconds=30))
    with patch("homeassistant.components.icloud.account.dispatcher_send", record):
        await next_fetch(hass, freezer)

    assert seen == [device.location]
    assert device.location is not None


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
    locating_service: tuple,
    freezer: FrozenDateTimeFactory,
    timestamp: object,
) -> None:
    """Test that a timestamp that is there but cannot be read does not end the poll.

    iCloud has no reason to send anything but a number, but arithmetic on
    anything else raises inside the poll. A fix that cannot be dated is kept,
    the same as one that carries no timestamp at all.
    """
    _, status = locating_service
    await setup_account(hass)

    status["location"] = location(
        is_old=True, age=timedelta(minutes=DEFAULT_MAX_INTERVAL * 3)
    ) | {"timeStamp": timestamp}
    await next_fetch(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_LATITUDE] == 1.0
    assert state.attributes[ATTR_LONGITUDE] == 2.0
