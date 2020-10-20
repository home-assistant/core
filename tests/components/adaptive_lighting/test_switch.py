"""Tests for Adaptive Lighting switches."""
# pylint: disable=protected-access
import asyncio
import datetime
from random import randint

import pytest

from homeassistant.components.adaptive_lighting.const import (
    ATTR_TURN_ON_OFF_LISTENER,
    CONF_DETECT_NON_HA_CHANGES,
    CONF_INITIAL_TRANSITION,
    CONF_MANUAL_CONTROL,
    CONF_PREFER_RGB_COLOR,
    CONF_SUNRISE_OFFSET,
    CONF_SUNRISE_TIME,
    CONF_SUNSET_TIME,
    CONF_TRANSITION,
    CONF_TURN_ON_LIGHTS,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_NAME,
    DEFAULT_SLEEP_BRIGHTNESS,
    DEFAULT_SLEEP_COLOR_TEMP,
    DOMAIN,
    SERVICE_APPLY,
    SERVICE_SET_MANUAL_CONTROL,
    SLEEP_MODE_SWITCH,
    UNDO_UPDATE_LISTENER,
)
from homeassistant.components.adaptive_lighting.switch import (
    _attributes_have_changed,
    _expand_light_groups,
    color_difference_redmean,
    create_context,
    is_our_context,
)
from homeassistant.components.demo.light import DemoLight
from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
import homeassistant.config as config_util
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.components.demo.test_light import ENTITY_LIGHT

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

ENTITY_SWITCH = f"{SWITCH_DOMAIN}.{DOMAIN}_{DEFAULT_NAME}"
ENTITY_SLEEP_MODE_SWITCH = f"{SWITCH_DOMAIN}.{DOMAIN}_sleep_mode_{DEFAULT_NAME}"

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE


@pytest.fixture
def reset_time_zone():
    """Reset time zone."""
    yield
    dt_util.DEFAULT_TIME_ZONE = ORIG_TIMEZONE


async def setup_switch(hass, extra_data):
    """Create the switch entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: DEFAULT_NAME, **extra_data})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    switch = hass.data[DOMAIN][entry.entry_id][SWITCH_DOMAIN]
    return entry, switch


async def setup_lights(hass):
    """Set up 3 light entities using the 'test' platform."""
    platform = getattr(hass.components, "test.light")
    while platform.ENTITIES:
        # Make sure it is empty
        platform.ENTITIES.pop()
    lights = [
        DemoLight(
            unique_id="light_1",
            name="Bed Light",
            state=True,
            ct=200,
        ),
        DemoLight(
            unique_id="light_2",
            name="Ceiling Lights",
            state=True,
            ct=380,
        ),
        DemoLight(
            unique_id="light_3",
            name="Kitchen Lights",
            state=True,
            hs_color=(345, 75),
            ct=240,
        ),
    ]
    platform.ENTITIES.extend(lights)
    assert await async_setup_component(
        hass, LIGHT_DOMAIN, {LIGHT_DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()
    return lights


async def setup_lights_and_switch(hass):
    """Create switch and demo lights."""
    # Setup demo lights and turn on
    lights_instances = await setup_lights(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )

    # Setup switch
    lights = [
        "light.bed_light",
        "light.ceiling_lights",
    ]
    assert all(hass.states.get(light) is not None for light in lights)
    _, switch = await setup_switch(
        hass,
        {
            CONF_LIGHTS: lights,
            CONF_SUNRISE_TIME: datetime.time(SUNRISE.hour),
            CONF_SUNSET_TIME: datetime.time(SUNSET.hour),
            CONF_INITIAL_TRANSITION: 0,
            CONF_TRANSITION: 0,
            CONF_DETECT_NON_HA_CHANGES: True,
            CONF_PREFER_RGB_COLOR: False,
        },
    )
    await hass.async_block_till_done()
    return switch, lights_instances


async def test_adaptive_lighting_switches(hass):
    """Test switches created for adaptive_lighting integration."""
    entry, _ = await setup_switch(hass, {})

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    assert hass.states.async_entity_ids(SWITCH_DOMAIN) == [
        ENTITY_SWITCH,
        ENTITY_SLEEP_MODE_SWITCH,
    ]
    assert ATTR_TURN_ON_OFF_LISTENER in hass.data[DOMAIN]
    assert entry.entry_id in hass.data[DOMAIN]
    assert len(hass.data[DOMAIN].keys()) == 2

    data = hass.data[DOMAIN][entry.entry_id]
    assert SLEEP_MODE_SWITCH in data
    assert SWITCH_DOMAIN in data
    assert UNDO_UPDATE_LISTENER in data
    assert len(data.keys()) == 3


@pytest.mark.parametrize("lat,long,timezone", LAT_LONG_TZS)
async def test_adaptive_lighting_time_zones_with_default_settings(
    hass, lat, long, timezone, reset_time_zone  # pylint: disable=redefined-outer-name
):
    """Test setting up the Adaptive Lighting switches with different timezones."""
    await config_util.async_process_ha_core_config(
        hass,
        {"latitude": lat, "longitude": long, "time_zone": timezone},
    )
    _, switch = await setup_switch(hass, {})
    # Shouldn't raise an exception ever
    await switch._update_attrs_and_maybe_adapt_lights(
        context=switch.create_context("test")
    )


@pytest.mark.parametrize("lat,long,timezone", LAT_LONG_TZS)
async def test_adaptive_lighting_time_zones_and_sun_settings(
    hass, lat, long, timezone, reset_time_zone  # pylint: disable=redefined-outer-name
):
    """Test setting up the Adaptive Lighting switches with different timezones.

    Also test the (sleep) brightness and color temperature settings.
    """
    await config_util.async_process_ha_core_config(
        hass,
        {"latitude": lat, "longitude": long, "time_zone": timezone},
    )
    _, switch = await setup_switch(
        hass,
        {
            CONF_SUNRISE_TIME: datetime.time(SUNRISE.hour),
            CONF_SUNSET_TIME: datetime.time(SUNSET.hour),
        },
    )

    context = switch.create_context("test")  # needs to be passed to update method
    min_color_temp = switch._sun_light_settings.min_color_temp

    sunset = hass.config.time_zone.localize(SUNSET).astimezone(dt_util.UTC)
    before_sunset = sunset - datetime.timedelta(hours=1)
    after_sunset = sunset + datetime.timedelta(hours=1)
    sunrise = hass.config.time_zone.localize(SUNRISE).astimezone(dt_util.UTC)
    before_sunrise = sunrise - datetime.timedelta(hours=1)
    after_sunrise = sunrise + datetime.timedelta(hours=1)

    async def patch_time_and_update(time):
        with patch("homeassistant.util.dt.utcnow", return_value=time):
            await switch._update_attrs_and_maybe_adapt_lights(context=context)
            await hass.async_block_till_done()

    # At sunset the brightness should be max and color_temp at the smallest value
    await patch_time_and_update(sunset)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] == min_color_temp

    # One hour before sunset the brightness should be max and color_temp
    # not at the smallest value yet.
    await patch_time_and_update(before_sunset)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] > min_color_temp

    # One hour after sunset the brightness should be down
    await patch_time_and_update(after_sunset)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] < DEFAULT_MAX_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] == min_color_temp

    # At sunrise the brightness should be max and color_temp at the smallest value
    await patch_time_and_update(sunrise)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] == min_color_temp

    # One hour before sunrise the brightness should smaller than max
    # and color_temp at the min value.
    await patch_time_and_update(before_sunrise)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] < DEFAULT_MAX_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] == min_color_temp

    # One hour after sunrise the brightness should be up
    await patch_time_and_update(after_sunrise)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_MAX_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] > min_color_temp

    # Turn on sleep mode which make the brightness and color_temp
    # deterministic regardless of the time
    await switch.sleep_mode_switch.async_turn_on()
    await switch._update_attrs_and_maybe_adapt_lights(context=context)
    assert switch._settings[ATTR_BRIGHTNESS_PCT] == DEFAULT_SLEEP_BRIGHTNESS
    assert switch._settings["color_temp_kelvin"] == DEFAULT_SLEEP_COLOR_TEMP


async def test_light_settings(hass):
    """Test that light settings are correctly applied."""
    switch, _ = await setup_lights_and_switch(hass)
    lights = switch._lights

    # Turn on "sleep mode"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_SLEEP_MODE_SWITCH},
        blocking=True,
    )
    await hass.async_block_till_done()
    light_states = [hass.states.get(light) for light in lights]
    for state in light_states:
        assert state.attributes[ATTR_BRIGHTNESS] == round(
            255 * switch._settings[ATTR_BRIGHTNESS_PCT] / 100
        )
        last_service_data = switch.turn_on_off_listener.last_service_data[
            state.entity_id
        ]
        assert state.attributes[ATTR_BRIGHTNESS] == last_service_data[ATTR_BRIGHTNESS]
        assert state.attributes[ATTR_COLOR_TEMP] == last_service_data[ATTR_COLOR_TEMP]

    # Turn off "sleep mode"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_SLEEP_MODE_SWITCH},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Test with different times
    sunset = hass.config.time_zone.localize(SUNSET).astimezone(dt_util.UTC)
    before_sunset = sunset - datetime.timedelta(hours=1)
    after_sunset = sunset + datetime.timedelta(hours=1)
    sunrise = hass.config.time_zone.localize(SUNRISE).astimezone(dt_util.UTC)
    before_sunrise = sunrise - datetime.timedelta(hours=1)
    after_sunrise = sunrise + datetime.timedelta(hours=1)

    context = switch.create_context("test")  # needs to be passed to update method

    async def patch_time_and_get_updated_states(time):
        with patch("homeassistant.util.dt.utcnow", return_value=time):
            await switch._update_attrs_and_maybe_adapt_lights(
                transition=0, context=context, force=True
            )
            await hass.async_block_till_done()
            return [hass.states.get(light) for light in lights]

    def assert_expected_color_temp(state):
        last_service_data = switch.turn_on_off_listener.last_service_data[
            state.entity_id
        ]
        assert state.attributes[ATTR_COLOR_TEMP] == last_service_data[ATTR_COLOR_TEMP]

    # At sunset the brightness should be max and color_temp at the smallest value
    light_states = await patch_time_and_get_updated_states(sunset)
    for state in light_states:
        assert state.attributes[ATTR_BRIGHTNESS] == 255
        assert_expected_color_temp(state)

    # One hour before sunset the brightness should be max and color_temp
    # not at the smallest value yet.
    light_states = await patch_time_and_get_updated_states(before_sunset)
    for state in light_states:
        assert state.attributes[ATTR_BRIGHTNESS] == 255
        assert_expected_color_temp(state)

    # One hour after sunset the brightness should be down
    light_states = await patch_time_and_get_updated_states(after_sunset)
    for state in light_states:
        assert state.attributes[ATTR_BRIGHTNESS] < 255
        assert_expected_color_temp(state)

    # At sunrise the brightness should be max and color_temp at the smallest value
    light_states = await patch_time_and_get_updated_states(sunrise)
    for state in light_states:
        assert state.attributes[ATTR_BRIGHTNESS] == 255
        assert_expected_color_temp(state)

    # One hour before sunrise the brightness should smaller than max
    # and color_temp at the min value.
    light_states = await patch_time_and_get_updated_states(before_sunrise)
    for state in light_states:
        assert state.attributes[ATTR_BRIGHTNESS] < 255
        assert_expected_color_temp(state)

    # One hour after sunrise the brightness should be up
    light_states = await patch_time_and_get_updated_states(after_sunrise)
    for state in light_states:
        assert state.attributes[ATTR_BRIGHTNESS] == 255
        assert_expected_color_temp(state)


async def test_turn_on_off_listener_not_tracking_untracked_lights(hass):
    """Test that lights that are not in a Adaptive Lighting switch aren't tracked."""
    switch, _ = await setup_lights_and_switch(hass)
    light = "light.kitchen_lights"
    assert light not in switch._lights
    for state in [True, False]:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON if state else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: light},
            blocking=True,
        )
        await switch._update_attrs_and_maybe_adapt_lights(
            context=switch.create_context("test")
        )
        await hass.async_block_till_done()
    assert light not in switch.turn_on_off_listener.lights


async def test_manual_control(hass):
    """Test the 'manual control' tracking."""
    switch, _ = await setup_lights_and_switch(hass)
    context = switch.create_context("test")  # needs to be passed to update method

    async def update():
        await switch._update_attrs_and_maybe_adapt_lights(transition=0, context=context)
        await hass.async_block_till_done()

    async def turn_light(state):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON if state else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_LIGHT},
            blocking=True,
        )
        await hass.async_block_till_done()
        await update()

    async def turn_switch(state, entity_id):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON if state else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    async def change_manual_control(set_to):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MANUAL_CONTROL,
            {
                ATTR_ENTITY_ID: switch.entity_id,
                CONF_MANUAL_CONTROL: set_to,
                CONF_LIGHTS: [ENTITY_LIGHT],
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        await update()

    # Nothing is manually controlled
    await update()
    assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]
    # Call light.turn_on for ENTITY_LIGHT
    await turn_light(True)
    # Check that ENTITY_LIGHT is manually controlled
    assert switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]
    # Test adaptive_lighting.set_manual_control
    await change_manual_control(False)
    # Check that ENTITY_LIGHT is not manually controlled
    assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]

    # Check that toggling light off to on resets manual control
    await change_manual_control(True)
    assert switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]
    await turn_light(False)
    await turn_light(True)
    assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]

    # Check that toggling (sleep mode) switch resets manual control
    for entity_id in [ENTITY_SWITCH, ENTITY_SLEEP_MODE_SWITCH]:
        await change_manual_control(True)
        assert switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]
        await turn_switch(False, entity_id)
        await turn_switch(True, entity_id)
        assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]


async def test_apply_service(hass):
    """Test adaptive_lighting.apply service."""
    await setup_lights_and_switch(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_APPLY,
        {
            ATTR_ENTITY_ID: ENTITY_SWITCH,
            CONF_LIGHTS: [ENTITY_LIGHT],
            CONF_TURN_ON_LIGHTS: True,
        },
        blocking=True,
    )


async def test_switch_off_on_off(hass):
    """Test switch rapid off_on_off."""

    async def turn_light(state, **kwargs):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON if state else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, **kwargs},
            blocking=True,
        )
        await hass.async_block_till_done()

    async def update():
        await switch._update_attrs_and_maybe_adapt_lights(
            transition=0, context=switch.create_context("test")
        )
        await hass.async_block_till_done()

    switch, _ = await setup_lights_and_switch(hass)

    for turn_light_state_at_end in [True, False]:
        # Turn light on
        await turn_light(True)
        # Turn light off with transition
        await turn_light(False, transition=1)

        assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]
        # Set state to on after a second (like happens IRL)
        await asyncio.sleep(1e-3)
        hass.states.async_set(ENTITY_LIGHT, STATE_ON)
        # Set state to off after a second (like happens IRL)
        await asyncio.sleep(1e-3)
        hass.states.async_set(ENTITY_LIGHT, STATE_OFF)

        # Now we test whether the sleep task is there
        assert ENTITY_LIGHT in switch.turn_on_off_listener.sleep_tasks
        sleep_task = switch.turn_on_off_listener.sleep_tasks[ENTITY_LIGHT]
        assert not sleep_task.cancelled()

        # A 'light.turn_on' event should cancel that task
        await turn_light(turn_light_state_at_end)
        await update()
        state = hass.states.get(ENTITY_LIGHT).state
        if turn_light_state_at_end:
            assert sleep_task.cancelled()
            assert state == STATE_ON
        else:
            assert state == STATE_OFF


async def test_significant_change(hass):
    """Test significant change."""

    async def turn_light(state, **kwargs):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON if state else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, **kwargs},
            blocking=True,
        )
        await hass.async_block_till_done()

    async def update(force):
        await switch._update_attrs_and_maybe_adapt_lights(
            transition=0,
            context=switch.create_context("test"),
            force=force,
        )
        await hass.async_block_till_done()

    switch, (bed_light_instance, *_) = await setup_lights_and_switch(hass)
    await turn_light(True)
    await update(force=True)  # removes manual control
    assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]

    # Change brightness by setting state (not using 'light.turn_on')
    attributes = hass.states.get(ENTITY_LIGHT).attributes
    new_attributes = attributes.copy()
    new_brightness = (attributes[ATTR_BRIGHTNESS] + 100) % 255
    new_attributes[ATTR_BRIGHTNESS] = new_brightness
    bed_light_instance._brightness = new_brightness
    assert switch.turn_on_off_listener.last_service_data.get(ENTITY_LIGHT) is not None
    for _ in range(switch.turn_on_off_listener.max_cnt_significant_changes):
        await update(force=False)
        assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]
    # On next update the light should be marked as manually controlled
    await update(force=False)
    assert not switch.turn_on_off_listener.manual_control[ENTITY_LIGHT]


def test_color_difference_redmean():
    """Test color_difference_redmean function."""
    for _ in range(10):
        rgb_1 = (randint(0, 255), randint(0, 255), randint(0, 255))
        rgb_2 = (randint(0, 255), randint(0, 255), randint(0, 255))
        color_difference_redmean(rgb_1, rgb_2)
    color_difference_redmean((0, 0, 0), (255, 255, 255))


def test_is_our_context():
    """Test is_our_context function."""
    context = create_context(DOMAIN, "test", 0)
    assert is_our_context(context)
    assert not is_our_context(None)
    assert not is_our_context(Context())


def test_attributes_have_changed():
    """Test _attributes_have_changed function."""
    attributes_1 = {ATTR_BRIGHTNESS: 1, ATTR_RGB_COLOR: (0, 0, 0), ATTR_COLOR_TEMP: 100}
    attributes_2 = {
        ATTR_BRIGHTNESS: 100,
        ATTR_RGB_COLOR: (255, 0, 0),
        ATTR_COLOR_TEMP: 300,
    }
    kwargs = dict(
        light="light.test",
        adapt_brightness=True,
        adapt_color_temp=True,
        adapt_rgb_color=True,
        context=Context(),
    )
    assert not _attributes_have_changed(
        old_attributes=attributes_1, new_attributes=attributes_1, **kwargs
    )
    for key, value in attributes_2.items():
        attrs = dict(attributes_1)
        attrs[key] = value
        assert _attributes_have_changed(
            old_attributes=attributes_1, new_attributes=attrs, **kwargs
        )
    # Switch from rgb_color to color_temp
    assert _attributes_have_changed(
        old_attributes={ATTR_BRIGHTNESS: 1, ATTR_COLOR_TEMP: 100},
        new_attributes={ATTR_BRIGHTNESS: 1, ATTR_RGB_COLOR: (0, 0, 0)},
        **kwargs,
    )


@pytest.mark.parametrize("wait", [True, False])
async def test_expand_light_groups(hass, wait):
    """Test expanding light groups."""
    await setup_switch(hass, {})
    lights = ["light.ceiling_lights", "light.kitchen_lights"]
    await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {
            LIGHT_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": GROUP_DOMAIN,
                    "entities": lights,
                },
            ]
        },
    )
    if wait:
        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

    expanded = set(_expand_light_groups(hass, ["light.light_group"]))
    if wait:
        assert expanded == set(lights)
    else:
        # Cannot expand yet because state is None
        assert expanded == {"light.light_group"}


async def test_unload_switch(hass):
    """Test removing Adaptive Lighting."""
    entry, _ = await setup_switch(hass, {})
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data


@pytest.mark.parametrize("state", [STATE_ON, STATE_OFF])
async def test_restore_off_state(hass, state):
    """Test that the 'off' and 'on' states are propoperly restored."""
    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=State(ENTITY_SWITCH, state),
    ):
        await hass.async_start()
        await hass.async_block_till_done()
        _, switch = await setup_switch(hass, {})
        if state == STATE_ON:
            assert switch.is_on
        else:
            assert not switch.is_on


@pytest.mark.xfail(reason="Offset is larger than half a day")
async def test_offset_too_large(hass):
    """Test that update fails when the offset is too large."""
    _, switch = await setup_switch(hass, {CONF_SUNRISE_OFFSET: 3600 * 12})
    await switch._update_attrs_and_maybe_adapt_lights(
        context=switch.create_context("test")
    )
    await hass.async_block_till_done()


async def test_turn_on_and_off_when_already_at_that_state(hass):
    """Test 'switch.turn_on/off' when switch is on/off."""
    _, switch = await setup_switch(hass, {})

    await switch.async_turn_on()
    await hass.async_block_till_done()
    await switch.async_turn_on()
    await hass.async_block_till_done()

    await switch.async_turn_off()
    await hass.async_block_till_done()
    await switch.async_turn_off()
    await hass.async_block_till_done()


async def test_async_update_at_interval(hass):
    """Test '_async_update_at_interval' method."""
    _, switch = await setup_switch(hass, {})
    await switch._async_update_at_interval()
