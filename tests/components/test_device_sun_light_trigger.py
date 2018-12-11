"""The tests device sun light trigger component."""
# pylint: disable=protected-access
from datetime import datetime
from asynctest import patch
import pytest

from homeassistant.setup import async_setup_component
import homeassistant.loader as loader
from homeassistant.const import CONF_PLATFORM, STATE_HOME, STATE_NOT_HOME
from homeassistant.components import (
    device_tracker, light, device_sun_light_trigger)
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.light import common as common_light


@pytest.fixture
def scanner(hass):
    """Initialize components."""
    scanner = loader.get_component(
        hass, 'device_tracker.test').get_scanner(None, None)

    scanner.reset()
    scanner.come_home('DEV1')

    loader.get_component(hass, 'light.test').init()

    with patch(
        'homeassistant.components.device_tracker.load_yaml_config_file',
        return_value={
            'device_1': {
                'hide_if_away': False,
                'mac': 'DEV1',
                'name': 'Unnamed Device',
                'picture': 'http://example.com/dev1.jpg',
                'track': True,
                'vendor': None
            },
            'device_2': {
                'hide_if_away': False,
                'mac': 'DEV2',
                'name': 'Unnamed Device',
                'picture': 'http://example.com/dev2.jpg',
                'track': True,
                'vendor': None}
            }):
        assert hass.loop.run_until_complete(async_setup_component(
            hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {CONF_PLATFORM: 'test'}
            }))

    assert hass.loop.run_until_complete(async_setup_component(
        hass, light.DOMAIN, {
            light.DOMAIN: {CONF_PLATFORM: 'test'}
        }))

    return scanner


async def test_lights_on_when_sun_sets(hass, scanner):
    """Test lights go on when there is someone home and the sun sets."""
    test_time = datetime(2017, 4, 5, 1, 2, 3, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow', return_value=test_time):
        assert await async_setup_component(
            hass, device_sun_light_trigger.DOMAIN, {
                device_sun_light_trigger.DOMAIN: {}})

    common_light.async_turn_off(hass)

    await hass.async_block_till_done()

    test_time = test_time.replace(hour=3)
    with patch('homeassistant.util.dt.utcnow', return_value=test_time):
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()

    assert light.is_on(hass)


async def test_lights_turn_off_when_everyone_leaves(hass, scanner):
    """Test lights turn off when everyone leaves the house."""
    common_light.async_turn_on(hass)

    await hass.async_block_till_done()

    assert await async_setup_component(
        hass, device_sun_light_trigger.DOMAIN, {
            device_sun_light_trigger.DOMAIN: {}})

    hass.states.async_set(device_tracker.ENTITY_ID_ALL_DEVICES,
                          STATE_NOT_HOME)

    await hass.async_block_till_done()

    assert not light.is_on(hass)


async def test_lights_turn_on_when_coming_home_after_sun_set(hass, scanner):
    """Test lights turn on when coming home after sun set."""
    test_time = datetime(2017, 4, 5, 3, 2, 3, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow', return_value=test_time):
        common_light.async_turn_off(hass)
        await hass.async_block_till_done()

        assert await async_setup_component(
            hass, device_sun_light_trigger.DOMAIN, {
                device_sun_light_trigger.DOMAIN: {}})

        hass.states.async_set(
            device_tracker.ENTITY_ID_FORMAT.format('device_2'), STATE_HOME)

        await hass.async_block_till_done()
    assert light.is_on(hass)
