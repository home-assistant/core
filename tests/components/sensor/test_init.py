"""Test sensor category setup.

Particularly test the category-wide service for forcing immediate
sensor update.
"""
import logging

# Importing pytest has side-effects, but pylint doesn't know that
import pytest # noqa # pylint: disable=unused-import
from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.sensor import SERVICE_FORCE_UPDATE
from homeassistant.bootstrap import async_setup_component

_LOGGER = logging.getLogger(__name__)


async def test_sensor_force_update(hass, requests_mock):
    """Test using a service event to force an update."""
    config = {
        'sensor': {
            'name': 'test',
            'platform': 'rest',
            'resource': 'http://localhost/'
            }
        }

    requests_mock.get('http://localhost/', status_code=200, text='1')

    await async_setup_component(hass, SENSOR, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert requests_mock.call_count == 2

    await hass.services.async_call(SENSOR, SERVICE_FORCE_UPDATE,
                                   {ATTR_ENTITY_ID: 'sensor.test'})
    await hass.async_block_till_done()

    assert requests_mock.call_count == 3


async def test_sensor_force_update_non_existent(hass, requests_mock):
    """Test forcing an update on a non-existent sensor."""
    config = {
        'sensor': {
            'name': 'test',
            'platform': 'rest',
            'resource': 'http://localhost/'
            }
        }

    requests_mock.get('http://localhost/', status_code=200, text='1')

    with patch('homeassistant.components.sensor._LOGGER') as mock_logger:
        await async_setup_component(hass, SENSOR, config)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert requests_mock.call_count == 2

        await hass.services.async_call(SENSOR, SERVICE_FORCE_UPDATE,
                                       {ATTR_ENTITY_ID: 'sensor.dummy'})
        await hass.async_block_till_done()

        assert mock_logger.warning.called is True
        assert requests_mock.call_count == 2
