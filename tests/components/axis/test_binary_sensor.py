"""Axis binary sensor platform tests."""

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from .test_device import NAME, setup_axis_integration

PIR_INIT = b'<?xml version="1.0" encoding="UTF-8"?>\n<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">\n<tt:Event><wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics" xmlns:tnsaxis="http://www.axis.com/2009/event/topics" xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2" xmlns:wsa5="http://www.w3.org/2005/08/addressing"><wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">tns1:Device/tnsaxis:Sensor/PIR</wsnt:Topic><wsnt:ProducerReference><wsa5:Address>uri://94fbe18e-0af8-40d2-8539-67b6ea550c6e/ProducerReference</wsa5:Address></wsnt:ProducerReference><wsnt:Message><tt:Message UtcTime="2019-03-12T23:48:26.371215Z" PropertyOperation="Initialized"><tt:Source><tt:SimpleItem Name="sensor" Value="0"/></tt:Source><tt:Key></tt:Key><tt:Data><tt:SimpleItem Name="state" Value="0"/></tt:Data></tt:Message></wsnt:Message></wsnt:NotificationMessage></tt:Event></tt:MetadataStream>\n'
PTZ_PRESET_INIT = b'<?xml version="1.0" encoding="UTF-8"?>\n<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">\n<tt:Event><wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics" xmlns:tnsaxis="http://www.axis.com/2009/event/topics" xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2" xmlns:wsa5="http://www.w3.org/2005/08/addressing"><wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">tns1:PTZController/tnsaxis:PTZPresets/Channel_1</wsnt:Topic><wsnt:ProducerReference><wsa5:Address>uri://bf32a3b9-e5e7-4d57-a48d-1b5be9ae7b16/ProducerReference</wsa5:Address></wsnt:ProducerReference><wsnt:Message><tt:Message UtcTime="2020-11-03T20:21:48.346022Z" PropertyOperation="Initialized"><tt:Source><tt:SimpleItem Name="PresetToken" Value="1"/></tt:Source><tt:Key></tt:Key><tt:Data><tt:SimpleItem Name="on_preset" Value="1"/></tt:Data></tt:Message></wsnt:Message></wsnt:NotificationMessage></tt:Event></tt:MetadataStream>\n'
VMD4_C1P1_INIT = b'<?xml version="1.0" encoding="UTF-8"?>\n<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">\n<tt:Event><wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics" xmlns:tnsaxis="http://www.axis.com/2009/event/topics" xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2" xmlns:wsa5="http://www.w3.org/2005/08/addressing"><wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">tnsaxis:CameraApplicationPlatform/VMD/Camera1Profile1</wsnt:Topic><wsnt:ProducerReference><wsa5:Address>uri://94fbe18e-0af8-40d2-8539-67b6ea550c6e/ProducerReference</wsa5:Address></wsnt:ProducerReference><wsnt:Message><tt:Message UtcTime="2019-03-12T23:32:17.591253Z" PropertyOperation="Initialized"><tt:Source></tt:Source><tt:Key></tt:Key><tt:Data><tt:SimpleItem Name="active" Value="1"/></tt:Data></tt:Message></wsnt:Message></wsnt:NotificationMessage></tt:Event></tt:MetadataStream>\n'


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert (
        await async_setup_component(
            hass,
            BINARY_SENSOR_DOMAIN,
            {BINARY_SENSOR_DOMAIN: {"platform": AXIS_DOMAIN}},
        )
        is True
    )

    assert AXIS_DOMAIN not in hass.data


async def test_no_binary_sensors(hass):
    """Test that no sensors in Axis results in no sensor entities."""
    await setup_axis_integration(hass)

    assert not hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)


async def test_binary_sensors(hass, mock_axis_rtspclient):
    """Test that sensors are loaded properly."""
    await setup_axis_integration(hass)

    mock_axis_rtspclient(data=PIR_INIT)
    mock_axis_rtspclient(data=PTZ_PRESET_INIT)  # Not supported
    mock_axis_rtspclient(data=VMD4_C1P1_INIT)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 2

    pir = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_pir_0")
    assert pir.state == STATE_OFF
    assert pir.name == f"{NAME} PIR 0"
    assert pir.attributes["device_class"] == DEVICE_CLASS_MOTION

    vmd4 = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_vmd4_profile_1")
    assert vmd4.state == STATE_ON
    assert vmd4.name == f"{NAME} VMD4 Profile 1"
    assert vmd4.attributes["device_class"] == DEVICE_CLASS_MOTION
