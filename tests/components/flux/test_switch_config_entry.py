"""The tests for the Flux switch platform."""
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components import light, switch
from homeassistant.components.flux.config_flow import default_settings
from homeassistant.components.flux.const import (
    CONF_ADJUST_BRIGHTNESS,
    CONF_START_CT,
    CONF_STOP_CT,
    DOMAIN,
    MODE_MIRED,
    MODE_RGB,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_MODE,
    CONF_PLATFORM,
    SERVICE_TURN_ON,
    STATE_ON,
    SUN_EVENT_SUNRISE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
    mock_restore_cache,
)


async def setup_test_light_entities(hass: HomeAssistant, nr_lights):
    """Set up some lights for testing."""
    platform = getattr(hass.components, "test.light")
    platform.init()
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    lights = platform.ENTITIES

    for light_index in range(nr_lights):
        await hass.services.async_call(
            light.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: lights[light_index].entity_id},
            blocking=True,
        )

    await hass.async_block_till_done()

    for light_index in range(nr_lights):
        verify_initial_light_state(hass, lights[light_index])

    return lights[:nr_lights]


def verify_initial_light_state(hass: HomeAssistant, ent1):
    """Verify the state of a light."""
    state = hass.states.get(ent1.entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("brightness") is None


@pytest.fixture(autouse=True)
def set_utc(hass: HomeAssistant):
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


async def test_valid_config(hass: HomeAssistant) -> None:
    """Test configuration."""

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": ["light.desk", "light.lamp"],
        }
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_settings,
    )
    config_entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    state = hass.states.get("switch.flux")
    assert state
    assert state.state == "off"


async def test_restore_state_last_on(hass: HomeAssistant) -> None:
    """Test restoring state when the last state is on."""
    mock_restore_cache(hass, [State("switch.flux", "on")])

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": ["light.desk", "light.lamp"],
        }
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_settings,
    )
    config_entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    state = hass.states.get("switch.flux")
    assert state
    assert state.state == "on"


async def test_restore_state_last_off(hass: HomeAssistant) -> None:
    """Test restoring state when the last state is off."""
    mock_restore_cache(hass, [State("switch.flux", "off")])

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": ["light.desk", "light.lamp"],
        }
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_settings,
    )
    config_entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    state = hass.states.get("switch.flux")
    assert state
    assert state.state == "off"


async def test_valid_config_with_info(hass: HomeAssistant) -> None:
    """Test configuration."""
    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": ["light.desk", "light.lamp"],
            "stop_time": "22:59",
            "start_time": "7:22",
            "start_colortemp": "1000",
            "sunset_colortemp": "2000",
            "stop_colortemp": "4000",
        }
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_settings,
    )
    config_entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_flux_when_switch_is_off(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch when it is off."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=10, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    with freeze_time(test_time), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)

        config_settings = default_settings()
        config_settings.update(
            {
                "name": "flux",
                "lights": [ent1.entity_id],
            }
        )
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_settings,
        )
        config_entry.add_to_hass(hass)

        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()

    assert not turn_on_calls


async def update_lights(hass: HomeAssistant, config_settings, test_time, event_date):
    """Update the lights."""
    with freeze_time(test_time), patch(
        "homeassistant.components.flux.switch.get_astral_event_date",
        side_effect=event_date,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_settings,
        )
        config_entry.add_to_hass(hass)

        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.flux"},
            blocking=True,
        )
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
        return turn_on_calls


async def test_flux_before_sunrise(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch before sunrise."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=2, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=5)

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    await hass.async_block_till_done()
    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
        }
    )

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)

    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


async def test_flux_before_sunrise_known_location(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch before sunrise."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    hass.config.latitude = 55.948372
    hass.config.longitude = -3.199466
    hass.config.elevation = 17
    test_time = dt_util.utcnow().replace(
        hour=2, minute=0, second=0, day=21, month=6, year=2019
    )

    await hass.async_block_till_done()
    with freeze_time(test_time):
        config_settings = default_settings()
        config_settings.update(
            {
                "name": "flux",
                "lights": [ent1.entity_id],
            }
        )
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=config_settings,
        )
        config_entry.add_to_hass(hass)

        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
        turn_on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.flux"},
            blocking=True,
        )
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_after_sunrise_before_sunset(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch after sunrise and before sunset."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 173
    assert call.data[light.ATTR_XY_COLOR] == [0.439, 0.37]


# pylint: disable=invalid-name
async def test_flux_after_sunset_before_stop(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch after sunset and before stop."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "22:00",
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 146
    assert call.data[light.ATTR_XY_COLOR] == [0.506, 0.385]


# pylint: disable=invalid-name
async def test_flux_after_stop_before_sunrise(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch after stop and before sunrise."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=23, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_with_custom_start_stop_times(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux with custom start and stop times."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "start_time": "6:00",
            "stop_time": "23:30",
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 147
    assert call.data[light.ATTR_XY_COLOR] == [0.504, 0.385]


async def test_flux_before_sunrise_stop_next_day(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch before sunrise.

    This test has the stop_time on the next day (after midnight).
    """
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=2, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "01:00",
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_after_sunrise_before_sunset_stop_next_day(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch after sunrise and before sunset.

    This test has the stop_time on the next day (after midnight).
    """
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "01:00",
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 173
    assert call.data[light.ATTR_XY_COLOR] == [0.439, 0.37]


# pylint: disable=invalid-name
@pytest.mark.parametrize("x", [0, 1])
async def test_flux_after_sunset_before_midnight_stop_next_day(
    hass: HomeAssistant, x, enable_custom_integrations: None
) -> None:
    """Test the flux switch after sunset and before stop.

    This test has the stop_time on the next day (after midnight).
    """
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=23, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "01:00",
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 119
    assert call.data[light.ATTR_XY_COLOR] == [0.588, 0.386]


# pylint: disable=invalid-name
async def test_flux_after_sunset_after_midnight_stop_next_day(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch after sunset and before stop.

    This test has the stop_time on the next day (after midnight).
    """
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=00, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "01:00",
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 114
    assert call.data[light.ATTR_XY_COLOR] == [0.601, 0.382]


# pylint: disable=invalid-name
async def test_flux_after_stop_before_sunrise_stop_next_day(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch after stop and before sunrise.

    This test has the stop_time on the next day (after midnight).
    """
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=2, minute=30, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "01:00",
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 112
    assert call.data[light.ATTR_XY_COLOR] == [0.606, 0.379]


# pylint: disable=invalid-name
async def test_flux_with_custom_colortemps(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux with custom start and stop colortemps."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "22:00",
        }
    )

    config_settings[CONF_START_CT] = 1000
    config_settings[CONF_STOP_CT] = 6000

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 159
    assert call.data[light.ATTR_XY_COLOR] == [0.469, 0.378]


# pylint: disable=invalid-name
async def test_flux_with_brightness_adjust_disabled(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux with custom start and stop colortemps."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=17, minute=30, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
            "stop_time": "22:00",
        }
    )

    config_settings[CONF_ADJUST_BRIGHTNESS] = False

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert light.ATTR_BRIGHTNESS not in call.data
    assert call.data[light.ATTR_XY_COLOR] == [0.506, 0.385]


async def test_flux_with_multiple_lights(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch with multiple light entities."""
    ent1, ent2, ent3 = await setup_test_light_entities(hass, 3)

    test_time = dt_util.utcnow().replace(hour=12, minute=0, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id, ent2.entity_id, ent3.entity_id],
        }
    )

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_BRIGHTNESS] == 163
    assert call.data[light.ATTR_XY_COLOR] == [0.46, 0.376]
    call = turn_on_calls[-2]
    assert call.data[light.ATTR_BRIGHTNESS] == 163
    assert call.data[light.ATTR_XY_COLOR] == [0.46, 0.376]
    call = turn_on_calls[-3]
    assert call.data[light.ATTR_BRIGHTNESS] == 163
    assert call.data[light.ATTR_XY_COLOR] == [0.46, 0.376]


async def test_flux_with_mired(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch´s mode mired."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
        }
    )

    config_settings[CONF_MODE] = MODE_MIRED

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    assert call.data[light.ATTR_COLOR_TEMP] == 269


async def test_flux_with_rgb(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test the flux switch´s mode rgb."""
    ent1 = (await setup_test_light_entities(hass, 1))[0]

    test_time = dt_util.utcnow().replace(hour=8, minute=30, second=0)
    sunrise_time = test_time.replace(hour=5, minute=0, second=0)
    sunset_time = test_time.replace(hour=17, minute=0, second=0)

    config_settings = default_settings()
    config_settings.update(
        {
            "name": "flux",
            "lights": [ent1.entity_id],
        }
    )
    config_settings[CONF_MODE] = MODE_RGB

    def event_date(_, event, now=None):
        if event == SUN_EVENT_SUNRISE:
            return sunrise_time
        return sunset_time

    turn_on_calls = await update_lights(hass, config_settings, test_time, event_date)
    call = turn_on_calls[-1]
    rgb = (255, 198, 152)
    rounded_call = tuple(map(round, call.data[light.ATTR_RGB_COLOR]))
    assert rounded_call == rgb
