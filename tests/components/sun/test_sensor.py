"""The tests for the Sun sensor platform."""
from datetime import datetime, timedelta

from astral import LocationInfo
import astral.sun
from freezegun import freeze_time

from homeassistant.components import sun
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_setting_rising(hass: HomeAssistant) -> None:
    """Test retrieving sun setting and rising."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(utc_now):
        await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})

    await hass.async_block_till_done()

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

    state1 = hass.states.get("sensor.sun_next_dawn")
    state2 = hass.states.get("sensor.sun_next_dusk")
    state3 = hass.states.get("sensor.sun_next_midnight")
    state4 = hass.states.get("sensor.sun_next_noon")
    state5 = hass.states.get("sensor.sun_next_rising")
    state6 = hass.states.get("sensor.sun_next_setting")
    assert next_dawn.replace(microsecond=0) == dt_util.parse_datetime(state1.state)
    assert next_dusk.replace(microsecond=0) == dt_util.parse_datetime(state2.state)
    assert next_midnight.replace(microsecond=0) == dt_util.parse_datetime(state3.state)
    assert next_noon.replace(microsecond=0) == dt_util.parse_datetime(state4.state)
    assert next_rising.replace(microsecond=0) == dt_util.parse_datetime(state5.state)
    assert next_setting.replace(microsecond=0) == dt_util.parse_datetime(state6.state)

    entry_ids = hass.config_entries.async_entries("sun")

    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("sensor.sun_next_dawn")

    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-next_dawn"
