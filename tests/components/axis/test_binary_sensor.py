"""Axis binary sensor platform tests."""

from unittest.mock import Mock

from homeassistant import config_entries
from homeassistant.components import axis
from homeassistant.setup import async_setup_component

import homeassistant.components.binary_sensor as binary_sensor

EVENTS = [
    {
        'operation': 'Initialized',
        'topic': 'tns1:Device/tnsaxis:Sensor/PIR',
        'source': 'sensor',
        'source_idx': '0',
        'type': 'state',
        'value': '0'
    },
    {
        'operation': 'Initialized',
        'topic': 'tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile1',
        'type': 'active',
        'value': '1'
    }
]

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
        config_entry, 'binary_sensor')
    # To flush out the service call to update the group
    await hass.async_block_till_done()

    return device


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
    await setup_device(hass)

    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass):
    """Test that sensors are loaded properly."""
    device = await setup_device(hass)

    for event in EVENTS:
        device.api.stream.event.manage_event(event)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    pir = hass.states.get('binary_sensor.model_0_pir_0')
    assert pir.state == 'off'
    assert pir.name == 'model 0 PIR 0'

    vmd4 = hass.states.get('binary_sensor.model_0_vmd4_camera1profile1')
    assert vmd4.state == 'on'
    assert vmd4.name == 'model 0 VMD4 Camera1Profile1'
