"""Axis camera platform tests."""

from unittest.mock import Mock

from homeassistant import config_entries
from homeassistant.components import axis
from homeassistant.setup import async_setup_component

import homeassistant.components.camera as camera


ENTRY_CONFIG = {
    axis.CONF_DEVICE: {
        axis.config_flow.CONF_HOST: '1.2.3.4',
        axis.config_flow.CONF_USERNAME: 'user',
        axis.config_flow.CONF_PASSWORD: 'pass',
        axis.config_flow.CONF_PORT: 80
    },
    axis.config_flow.CONF_MAC: '1234ABCD',
    axis.config_flow.CONF_MODEL: 'model',
    axis.config_flow.CONF_NAME: 'model 0'
}

ENTRY_OPTIONS = {
    axis.CONF_CAMERA: False,
    axis.CONF_EVENTS: True,
    axis.CONF_TRIGGER_TIME: 0
}


async def setup_device(hass):
    """Load the Axis binary sensor platform."""
    from axis import AxisDevice
    loop = Mock()

    config_entry = config_entries.ConfigEntry(
        1, axis.DOMAIN, 'Mock Title', ENTRY_CONFIG, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH, options=ENTRY_OPTIONS)
    device = axis.AxisNetworkDevice(hass, config_entry)
    device.api = AxisDevice(loop=loop, **config_entry.data[axis.CONF_DEVICE],
                            signal=device.async_signal_callback)
    hass.data[axis.DOMAIN] = {device.serial: device}

    await hass.config_entries.async_forward_entry_setup(
        config_entry, 'camera')
    # To flush out the service call to update the group
    await hass.async_block_till_done()

    return device


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert await async_setup_component(hass, camera.DOMAIN, {
        'camera': {
            'platform': axis.DOMAIN
        }
    }) is True

    assert axis.DOMAIN not in hass.data


async def test_camera(hass):
    """Test that Axis camera platform is loaded properly."""
    await setup_device(hass)

    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    cam = hass.states.get('camera.model_0')
    assert cam.state == 'idle'
    assert cam.name == 'model 0'
