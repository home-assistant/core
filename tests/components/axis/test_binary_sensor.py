"""Axis binary sensor platform tests."""

from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import axis
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

import homeassistant.components.binary_sensor as binary_sensor

from tests.common import mock_coro


ENTRY_CONFIG = {
    axis.CONF_DEVICE: {
        axis.config_flow.CONF_HOST: '1.2.3.4',
        axis.config_flow.CONF_USERNAME: 'user',
        axis.config_flow.CONF_PASSWORD: 'pass',
        axis.config_flow.CONF_PORT: 80
    },
    axis.config_flow.CONF_MAC: '1234ABCD',
    axis.config_flow.CONF_MODEL_ID: 'model',
    axis.config_flow.CONF_NAME: 'model 0'
}

ENTRY_OPTIONS = {
    axis.CONF_CAMERA: False,
    axis.CONF_EVENTS: ['pir'],
    axis.CONF_TRIGGER_TIME: 0
}

async def setup_device(hass, data):
    """Load the Axis binary sensor platform."""
    from axis import AxisDevice
    loop = Mock()

    config_entry = config_entries.ConfigEntry(
        1, axis.DOMAIN, 'Mock Title', ENTRY_CONFIG, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH, options=ENTRY_OPTIONS)
    device = axis.AxisNetworkDevice(hass, config_entry)
    device.api = AxisDevice(loop=loop, **config_entry.data[axis.CONF_DEVICE])
    hass.data[axis.DOMAIN] = {device.serial: device}

    await hass.config_entries.async_forward_entry_setup(
        config_entry, 'binary_sensor')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert await async_setup_component(hass, binary_sensor.DOMAIN, {
        'binary_sensor': {
            'platform': axis.DOMAIN
        }
    }) is True
    assert axis.DOMAIN not in hass.data


async def test_no_binary_sensors(hass):
    """Test that no sensors in Axis results in no sensor entities."""
    data = {}
    await setup_device(hass, data)

    assert len(hass.states.async_all()) == 0
