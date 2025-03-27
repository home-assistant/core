"""The tests for the Sun sensor platform."""

from datetime import datetime, timedelta

from astral import LocationInfo
import astral.sun
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import sun
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setting_rising(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test retrieving sun setting and rising."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(utc_now)
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

    expected_solar_elevation = astral.sun.elevation(location.observer, utc_now)
    expected_solar_azimuth = astral.sun.azimuth(location.observer, utc_now)

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
    solar_elevation_state = hass.states.get("sensor.sun_solar_elevation")
    assert float(solar_elevation_state.state) == pytest.approx(
        expected_solar_elevation, 0.1
    )
    solar_azimuth_state = hass.states.get("sensor.sun_solar_azimuth")
    assert float(solar_azimuth_state.state) == pytest.approx(
        expected_solar_azimuth, 0.1
    )

    entry_ids = hass.config_entries.async_entries("sun")

    entity = entity_registry.async_get("sensor.sun_next_dawn")

    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-next_dawn"

    freezer.tick(timedelta(hours=24))
    # Block once for Sun to update
    await hass.async_block_till_done()
    # Block another time for the sensors to update
    await hass.async_block_till_done()

    # Make sure all the signals work
    assert state1.state != hass.states.get("sensor.sun_next_dawn").state
    assert state2.state != hass.states.get("sensor.sun_next_dusk").state
    assert state3.state != hass.states.get("sensor.sun_next_midnight").state
    assert state4.state != hass.states.get("sensor.sun_next_noon").state
    assert state5.state != hass.states.get("sensor.sun_next_rising").state
    assert state6.state != hass.states.get("sensor.sun_next_setting").state
    assert (
        solar_elevation_state.state
        != hass.states.get("sensor.sun_solar_elevation").state
    )
    assert (
        solar_azimuth_state.state != hass.states.get("sensor.sun_solar_azimuth").state
    )

    entity = entity_registry.async_get("sensor.sun_next_dusk")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-next_dusk"

    entity = entity_registry.async_get("sensor.sun_next_midnight")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-next_midnight"

    entity = entity_registry.async_get("sensor.sun_next_noon")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-next_noon"

    entity = entity_registry.async_get("sensor.sun_next_rising")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-next_rising"

    entity = entity_registry.async_get("sensor.sun_next_setting")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-next_setting"

    entity = entity_registry.async_get("sensor.sun_solar_elevation")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-solar_elevation"

    entity = entity_registry.async_get("sensor.sun_solar_azimuth")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-solar_azimuth"

    entity = entity_registry.async_get("sensor.sun_solar_rising")
    assert entity
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == f"{entry_ids[0].entry_id}-solar_rising"
