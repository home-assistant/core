"""The tests for the Sun component."""

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components import sun
from homeassistant.components.sun import entity
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setting_rising(hass: HomeAssistant) -> None:
    """Test retrieving sun setting and rising."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(utc_now):
        await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})

    await hass.async_block_till_done()
    state = hass.states.get(entity.ENTITY_ID)

    from astral import LocationInfo
    import astral.sun

    utc_today = utc_now.date()

    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    mod = -1
    while True:
        next_dawn = astral.sun.dawn(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_dawn > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_dusk = astral.sun.dusk(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_dusk > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_midnight = astral.sun.midnight(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_midnight > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_noon = astral.sun.noon(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_noon > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_rising = astral.sun.sunrise(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_rising > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_setting = astral.sun.sunset(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_setting > utc_now:
            break
        mod += 1

    assert next_dawn == dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_DAWN]
    )
    assert next_dusk == dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_DUSK]
    )
    assert next_midnight == dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_MIDNIGHT]
    )
    assert next_noon == dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_NOON]
    )
    assert next_rising == dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_RISING]
    )
    assert next_setting == dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_SETTING]
    )


async def test_state_change(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if the state changes at next setting/rising."""
    now = datetime(2016, 6, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})

    await hass.async_block_till_done()

    test_time = dt_util.parse_datetime(
        hass.states.get(entity.ENTITY_ID).attributes[entity.STATE_ATTR_NEXT_RISING]
    )
    assert test_time is not None

    assert hass.states.get(entity.ENTITY_ID).state == sun.STATE_BELOW_HORIZON

    patched_time = test_time + timedelta(seconds=5)
    with freeze_time(patched_time):
        async_fire_time_changed(hass, patched_time)
        await hass.async_block_till_done()

    assert hass.states.get(entity.ENTITY_ID).state == sun.STATE_ABOVE_HORIZON

    # Update core configuration
    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=now):
        await hass.config.async_update(longitude=hass.config.longitude + 90)
        await hass.async_block_till_done()

    assert hass.states.get(entity.ENTITY_ID).state == sun.STATE_ABOVE_HORIZON

    # Test listeners are not duplicated after a core configuration change
    test_time = dt_util.parse_datetime(
        hass.states.get(entity.ENTITY_ID).attributes[entity.STATE_ATTR_NEXT_DUSK]
    )
    assert test_time is not None

    patched_time = test_time + timedelta(seconds=5)
    caplog.clear()
    with freeze_time(patched_time):
        async_fire_time_changed(hass, patched_time)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert caplog.text.count("sun phase_update") == 1
    # Called once by time listener, once from Sun.update_events
    assert caplog.text.count("sun position_update") == 2

    assert hass.states.get(entity.ENTITY_ID).state == sun.STATE_BELOW_HORIZON


async def test_norway_in_june(hass: HomeAssistant) -> None:
    """Test location in Norway where the sun doesn't set in summer."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8

    june = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=june):
        assert await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})

    state = hass.states.get(entity.ENTITY_ID)
    assert state is not None

    assert dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_RISING]
    ) == datetime(2016, 7, 24, 22, 59, 45, 689645, tzinfo=dt_util.UTC)
    assert dt_util.parse_datetime(
        state.attributes[entity.STATE_ATTR_NEXT_SETTING]
    ) == datetime(2016, 7, 25, 22, 17, 13, 503932, tzinfo=dt_util.UTC)

    assert state.state == sun.STATE_ABOVE_HORIZON


@pytest.mark.skip
async def test_state_change_count(hass: HomeAssistant) -> None:
    """Count the number of state change events in a location."""
    # Skipped because it's a bit slow. Has been validated with
    # multiple lattitudes and dates
    hass.config.latitude = 10
    hass.config.longitude = 0

    now = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

    with freeze_time(now):
        assert await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})

    events = []

    @callback
    def state_change_listener(event):
        if event.data.get("entity_id") == "sun.sun":
            events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)
    await hass.async_block_till_done()

    for _ in range(24 * 60 * 60):
        now += timedelta(seconds=1)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

    assert len(events) < 721


async def test_setup_and_remove_config_entry(hass: HomeAssistant) -> None:
    """Test setting up and removing a config entry."""
    # Setup the config entry
    config_entry = MockConfigEntry(domain=sun.DOMAIN)
    config_entry.add_to_hass(hass)
    now = datetime(2016, 6, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Check the platform is setup correctly
    state = hass.states.get(entity.ENTITY_ID)
    assert state is not None

    test_time = dt_util.parse_datetime(
        hass.states.get(entity.ENTITY_ID).attributes[entity.STATE_ATTR_NEXT_RISING]
    )
    assert test_time is not None
    assert hass.states.get(entity.ENTITY_ID).state == sun.STATE_BELOW_HORIZON

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state is removed, and does not reappear
    assert hass.states.get(entity.ENTITY_ID) is None

    patched_time = test_time + timedelta(seconds=5)
    with freeze_time(patched_time):
        async_fire_time_changed(hass, patched_time)
        await hass.async_block_till_done()

    assert hass.states.get(entity.ENTITY_ID) is None
