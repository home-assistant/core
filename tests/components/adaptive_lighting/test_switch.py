"""Tests for Adaptive Lighting switches."""
import datetime

import pytest

from homeassistant.components.adaptive_lighting.const import (
    ATTR_TURN_ON_OFF_LISTENER,
    CONF_SUNRISE_TIME,
    CONF_SUNSET_TIME,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_NAME,
    DEFAULT_SLEEP_BRIGHTNESS,
    DEFAULT_SLEEP_COLOR_TEMP,
    DOMAIN,
    UNDO_UPDATE_LISTENER,
)
from homeassistant.components.light import ATTR_BRIGHTNESS_PCT
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
import homeassistant.config as config_util
from homeassistant.const import CONF_NAME
from homeassistant.core import Context
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import MockConfigEntry

SUNRISE = datetime.datetime(
    year=2020,
    month=10,
    day=17,
    hour=6,
)
SUNSET = datetime.datetime(
    year=2020,
    month=10,
    day=17,
    hour=22,
)

LAT_LONG_TZS = [
    (39, -1, "Europe/Madrid"),
    (60, 50, "GMT"),
    (55, 13, "Europe/Copenhagen"),
    (52.379189, 4.899431, "Europe/Amsterdam"),
    (32.87336, -117.22743, "US/Pacific"),
]


async def test_adaptive_lighting_switches(hass):
    """Test switches created for adaptive_lighting integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: DEFAULT_NAME})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    assert hass.states.async_entity_ids(SWITCH_DOMAIN) == [
        f"{SWITCH_DOMAIN}.{DOMAIN}_{DEFAULT_NAME}",
        f"{SWITCH_DOMAIN}.{DOMAIN}_sleep_mode_{DEFAULT_NAME}",
    ]
    assert ATTR_TURN_ON_OFF_LISTENER in hass.data[DOMAIN]
    assert entry.entry_id in hass.data[DOMAIN]
    assert len(hass.data[DOMAIN].keys()) == 2

    data = hass.data[DOMAIN][entry.entry_id]
    assert "sleep_mode_switch" in data
    assert SWITCH_DOMAIN in data
    assert UNDO_UPDATE_LISTENER in data
    assert len(data.keys()) == 3


@pytest.mark.parametrize("lat,long,tz", LAT_LONG_TZS)
async def test_adaptive_lighting_time_zones_and_sunsettings(hass, lat, long, tz):
    """Test setting up the Adaptive Lighting switches with different timezones.

    Also test the (sleep) brightness and color temperature settings.
    """
    await config_util.async_process_ha_core_config(
        hass,
        {"latitude": lat, "longitude": long, "time_zone": tz},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_SUNRISE_TIME: datetime.time(SUNRISE.hour),
            CONF_SUNSET_TIME: datetime.time(SUNSET.hour),
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    context = Context()  # needs to be passed to update method
    switch = hass.data[DOMAIN][entry.entry_id][SWITCH_DOMAIN]
    min_color_temp = switch._sun_light_settings.min_color_temp

    sunset = hass.config.time_zone.localize(SUNSET).astimezone(dt_util.UTC)
    before_sunset = sunset - datetime.timedelta(hours=1)
    after_sunset = sunset + datetime.timedelta(hours=1)
    sunrise = hass.config.time_zone.localize(SUNRISE).astimezone(dt_util.UTC)
    before_sunrise = sunrise - datetime.timedelta(hours=1)
    after_sunrise = sunrise + datetime.timedelta(hours=1)

    # At sunset the brightness should be max and color_temp at the smallest value
    with patch("homeassistant.util.dt.utcnow", return_value=sunset):
        await switch._update_attrs_and_maybe_adapt_lights(context=context)
        assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
        assert switch._settings["color_temp_kelvin"] == min_color_temp

    # One hour before sunset the brightness should be max and color_temp
    # not at the smallest value yet.
    with patch("homeassistant.util.dt.utcnow", return_value=before_sunset):
        await switch._update_attrs_and_maybe_adapt_lights(context=context)
        assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
        assert switch._settings["color_temp_kelvin"] > min_color_temp

    # One hour after sunset the brightness should be down
    with patch("homeassistant.util.dt.utcnow", return_value=after_sunset):
        await switch._update_attrs_and_maybe_adapt_lights(context=context)
        assert switch._settings[ATTR_BRIGHTNESS_PCT] < DEFAULT_MAX_BRIGHTNESS
        assert switch._settings["color_temp_kelvin"] == min_color_temp

    # At sunrise the brightness should be max and color_temp at the smallest value
    with patch("homeassistant.util.dt.utcnow", return_value=sunrise):
        await switch._update_attrs_and_maybe_adapt_lights(context=context)
        assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
        assert switch._settings["color_temp_kelvin"] == min_color_temp

    # One hour before sunrise the brightness should smaller than max
    # and color_temp at the min value.
    with patch("homeassistant.util.dt.utcnow", return_value=before_sunrise):
        await switch._update_attrs_and_maybe_adapt_lights(context=context)
        assert switch._settings[ATTR_BRIGHTNESS_PCT] < DEFAULT_MAX_BRIGHTNESS
        assert switch._settings["color_temp_kelvin"] == min_color_temp

    # One hour after sunrise the brightness should be up
    with patch("homeassistant.util.dt.utcnow", return_value=after_sunrise):
        await switch._update_attrs_and_maybe_adapt_lights(context=context)
        assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
        assert switch._settings["color_temp_kelvin"] > min_color_temp

    # Turn on sleep mode which make the brightness and color_temp
    # deterministic regardless of the time
    sleep_mode_switch = hass.data[DOMAIN][entry.entry_id]["sleep_mode_switch"]
    await sleep_mode_switch.async_turn_on()
    await switch._update_attrs_and_maybe_adapt_lights(context=context)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_SLEEP_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] == DEFAULT_SLEEP_COLOR_TEMP
