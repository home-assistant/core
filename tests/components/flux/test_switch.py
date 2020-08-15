"""The tests for the Flux switch platform."""
import pytest

from homeassistant.components import light, switch
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_TURN_ON,
    STATE_ON,
    SUN_EVENT_SUNRISE,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    async_mock_service,
    mock_restore_cache,
)
from tests.components.switch import common


async def test_valid_config(hass):
    """Test configuration."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "flux",
                "name": "flux",
                "lights": ["light.desk", "light.lamp"],
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("switch.flux")
    assert state
    assert state.state == "off"


async def test_restore_state_last_on(hass):
    """Test restoring state when the last state is on."""
    mock_restore_cache(hass, [State("switch.flux", "on")])

    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "flux",
                "name": "flux",
                "lights": ["light.desk", "light.lamp"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.flux")
    assert state
    assert state.state == "on"


async def test_restore_state_last_off(hass):
    """Test restoring state when the last state is off."""
    mock_restore_cache(hass, [State("switch.flux", "off")])

    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "flux",
                "name": "flux",
                "lights": ["light.desk", "light.lamp"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.flux")
    assert state
    assert state.state == "off"


async def test_valid_config_with_info(hass):
    """Test configuration."""
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "flux",
                "name": "flux",
                "lights": ["light.desk", "light.lamp"],
                "stop_time": "22:59",
                "start_time": "7:22",
                "start_colortemp": "1000",
                "sunset_colortemp": "2000",
                "stop_colortemp": "4000",
            }
        },
    )


async def test_valid_config_no_name(hass):
    """Test configuration."""
    with assert_setup_component(1, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {"switch": {"platform": "flux", "lights": ["light.desk", "light.lamp"]}},
        )


async def test_invalid_config_no_lights(hass):
    """Test configuration."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass, "switch", {"switch": {"platform": "flux", "name": "flux"}}
        )


async def test_flux_when_switch_is_off(hass):
    """Test the flux switch when it is off."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=10, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                }
            },
        )
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()

    assert not turn_on_calls


async def test_flux_before_sunrise(hass):
    """Test the flux switch before sunrise."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=2, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=5)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        await common.async_turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


async def test_flux_before_sunrise_known_location(hass):
    """Test the flux switch before sunrise."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    hass.config.latitude = 55.948372
    hass.config.longitude = -3.199466
    hass.config.elevation = 17
    test_time = dt_util.utcnow().replace(
        hour=2, minute=0, second=0, day=21, month=6, year=2019
    )

    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    # 'brightness': 255,
                    # 'disable_brightness_adjust': True,
                    # 'mode': 'rgb',
                    # 'interval': 120
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        await common.async_turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_after_sunrise_before_sunset(hass):
    """Test the flux switch after sunrise and before sunset."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        await common.async_turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 173
    assert call.data[light.ATTR_XY_COLOR] == [0.439, 0.37]


# pylint: disable=invalid-name
async def test_flux_after_sunset_before_stop(hass):
    """Test the flux switch after sunset and before stop."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "stop_time": "22:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 146
    assert call.data[light.ATTR_XY_COLOR] == [0.506, 0.385]


# pylint: disable=invalid-name
async def test_flux_after_stop_before_sunrise(hass):
    """Test the flux switch after stop and before sunrise."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=23, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_with_custom_start_stop_times(hass):
    """Test the flux with custom start and stop times."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "start_time": "6:00",
                    "stop_time": "23:30",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 147
    assert call.data[light.ATTR_XY_COLOR] == [0.504, 0.385]


async def test_flux_before_sunrise_stop_next_day(hass):
    """Test the flux switch before sunrise.

    This test has the stop_time on the next day (after midnight).
    """
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=2, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "stop_time": "01:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_after_sunrise_before_sunset_stop_next_day(hass):
    """
    Test the flux switch after sunrise and before sunset.

    This test has the stop_time on the next day (after midnight).
    """
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "stop_time": "01:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 173
    assert call.data[light.ATTR_XY_COLOR] == [0.439, 0.37]


# pylint: disable=invalid-name
@pytest.mark.parametrize("x", [0, 1])
async def test_flux_after_sunset_before_midnight_stop_next_day(hass, x):
    """Test the flux switch after sunset and before stop.

    This test has the stop_time on the next day (after midnight).
    """
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=23, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "stop_time": "01:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 119
    assert call.data[light.ATTR_XY_COLOR] == [0.588, 0.386]


# pylint: disable=invalid-name
async def test_flux_after_sunset_after_midnight_stop_next_day(hass):
    """Test the flux switch after sunset and before stop.

    This test has the stop_time on the next day (after midnight).
    """
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=00, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "stop_time": "01:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 114
    assert call.data[light.ATTR_XY_COLOR] == [0.601, 0.382]


# pylint: disable=invalid-name
async def test_flux_after_stop_before_sunrise_stop_next_day(hass):
    """Test the flux switch after stop and before sunrise.

    This test has the stop_time on the next day (after midnight).
    """
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=2, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "stop_time": "01:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_with_custom_colortemps(hass):
    """Test the flux with custom start and stop colortemps."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "start_colortemp": "1000",
                    "stop_colortemp": "6000",
                    "stop_time": "22:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 159
    assert call.data[light.ATTR_XY_COLOR] == [0.469, 0.378]


# pylint: disable=invalid-name
async def test_flux_with_custom_brightness(hass):
    """Test the flux with custom start and stop colortemps."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "brightness": 255,
                    "stop_time": "22:00",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 255
    assert call.data[light.ATTR_XY_COLOR] == [0.506, 0.385]


async def test_flux_with_multiple_lights(hass):
    """Test the flux switch with multiple light entities."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1, ent2, ent3 = platform.ENTITIES

    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ent2.entity_id}, blocking=True
    )
    await hass.services.async_call(
        light.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ent3.entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    state = hass.states.get(ent2.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    state = hass.states.get(ent3.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None

    test_time = dt_util.utcnow().replace(hour=12, minute=0, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            print(f"sunrise {sunrise_time}")
            return sunrise_time
        print(f"sunset {sunset_time}")
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id, ent2.entity_id, ent3.entity_id],
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 163
    assert call.data[light.ATTR_XY_COLOR] == [0.46, 0.376]
    call = turn_on_calls[-2]
    assert call.data[light.ATTR_BRIGHTNESS] == 163
    assert call.data[light.ATTR_XY_COLOR] == [0.46, 0.376]
    call = turn_on_calls[-3]
    assert call.data[light.ATTR_BRIGHTNESS] == 163
    assert call.data[light.ATTR_XY_COLOR] == [0.46, 0.376]


async def test_flux_with_mired(hass):
    """Test the flux switch´s mode mired."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("color_temp") is None

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "mode": "mired",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        common.turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_COLOR_TEMP] == 269


async def test_flux_with_rgb(hass):
    """Test the flux switch´s mode rgb."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1 = platform.ENTITIES[0]

    # Verify initial state of light
    state = hass.states.get(ent1.entity_id)
    assert STATE_ON == state.state
    assert state.attributes.get("color_temp") is None

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(hass, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with patch(
        "homeassistant.components.flux.switch.dt_utcnow", return_value=test_time
    ), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "flux",
                    "name": "flux",
                    "lights": [ent1.entity_id],
                    "mode": "rgb",
                }
            },
        )
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        await common.async_turn_on(hass, "switch.flux")
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    rgb = (255, 198, 152)
    rounded_call = tuple(map(round, call.data[light.ATTR_RGB_COLOR]))
    assert rounded_call == rgb
