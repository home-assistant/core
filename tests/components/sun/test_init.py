"""The tests for the Sun component."""
from datetime import datetime, timedelta

from pytest import mark

import homeassistant.components.sun as sun
from homeassistant.const import EVENT_STATE_CHANGED
import homeassistant.core as ha
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch


async def test_setting_rising(hass):
    """Test retrieving sun setting and rising."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=utc_now):
        await async_setup_component(
            hass, sun.DOMAIN, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}}
        )

    await hass.async_block_till_done()
    state = hass.states.get(sun.ENTITY_ID)

    from astral import Astral

    astral = Astral()
    utc_today = utc_now.date()

    latitude = hass.config.latitude
    longitude = hass.config.longitude

    mod = -1
    while True:
        next_dawn = astral.dawn_utc(
            utc_today + timedelta(days=mod), latitude, longitude
        )
        if next_dawn > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_dusk = astral.dusk_utc(
            utc_today + timedelta(days=mod), latitude, longitude
        )
        if next_dusk > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_midnight = astral.solar_midnight_utc(
            utc_today + timedelta(days=mod), longitude
        )
        if next_midnight > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_noon = astral.solar_noon_utc(utc_today + timedelta(days=mod), longitude)
        if next_noon > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_rising = astral.sunrise_utc(
            utc_today + timedelta(days=mod), latitude, longitude
        )
        if next_rising > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_setting = astral.sunset_utc(
            utc_today + timedelta(days=mod), latitude, longitude
        )
        if next_setting > utc_now:
            break
        mod += 1

    assert next_dawn == dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_DAWN]
    )
    assert next_dusk == dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_DUSK]
    )
    assert next_midnight == dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_MIDNIGHT]
    )
    assert next_noon == dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_NOON]
    )
    assert next_rising == dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_RISING]
    )
    assert next_setting == dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_SETTING]
    )


async def test_state_change(hass):
    """Test if the state changes at next setting/rising."""
    now = datetime(2016, 6, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=now):
        await async_setup_component(
            hass, sun.DOMAIN, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}}
        )

    await hass.async_block_till_done()

    test_time = dt_util.parse_datetime(
        hass.states.get(sun.ENTITY_ID).attributes[sun.STATE_ATTR_NEXT_RISING]
    )
    assert test_time is not None

    assert sun.STATE_BELOW_HORIZON == hass.states.get(sun.ENTITY_ID).state

    hass.bus.async_fire(
        ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: test_time + timedelta(seconds=5)}
    )

    await hass.async_block_till_done()

    assert sun.STATE_ABOVE_HORIZON == hass.states.get(sun.ENTITY_ID).state

    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=now):
        await hass.config.async_update(longitude=hass.config.longitude + 90)
        await hass.async_block_till_done()

    assert sun.STATE_ABOVE_HORIZON == hass.states.get(sun.ENTITY_ID).state


async def test_norway_in_june(hass):
    """Test location in Norway where the sun doesn't set in summer."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8

    june = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=june):
        assert await async_setup_component(
            hass, sun.DOMAIN, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}}
        )

    state = hass.states.get(sun.ENTITY_ID)
    assert state is not None

    assert dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_RISING]
    ) == datetime(2016, 7, 25, 23, 23, 39, tzinfo=dt_util.UTC)
    assert dt_util.parse_datetime(
        state.attributes[sun.STATE_ATTR_NEXT_SETTING]
    ) == datetime(2016, 7, 26, 22, 19, 1, tzinfo=dt_util.UTC)

    assert state.state == sun.STATE_ABOVE_HORIZON


@mark.skip
async def test_state_change_count(hass):
    """Count the number of state change events in a location."""
    # Skipped because it's a bit slow. Has been validated with
    # multiple lattitudes and dates
    hass.config.latitude = 10
    hass.config.longitude = 0

    now = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

    with patch("homeassistant.helpers.condition.dt_util.utcnow", return_value=now):
        assert await async_setup_component(
            hass, sun.DOMAIN, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}}
        )

    events = []

    @ha.callback
    def state_change_listener(event):
        if event.data.get("entity_id") == "sun.sun":
            events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, state_change_listener)
    await hass.async_block_till_done()

    for _ in range(24 * 60 * 60):
        now += timedelta(seconds=1)
        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})
        await hass.async_block_till_done()

    assert len(events) < 721
