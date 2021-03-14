"""Axis switch platform tests."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component

from .test_device import (
    API_DISCOVERY_PORT_MANAGEMENT,
    API_DISCOVERY_RESPONSE,
    NAME,
    setup_axis_integration,
)

RELAY_0_INIT = b'<?xml version="1.0" encoding="UTF-8"?>\n<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">\n<tt:Event><wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics" xmlns:tnsaxis="http://www.axis.com/2009/event/topics" xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2" xmlns:wsa5="http://www.w3.org/2005/08/addressing"><wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">tns1:Device/Trigger/Relay</wsnt:Topic><wsnt:ProducerReference><wsa5:Address>uri://4205c5dc-6132-44ad-9aa5-52172e062d2b/ProducerReference</wsa5:Address></wsnt:ProducerReference><wsnt:Message><tt:Message UtcTime="2019-04-22T20:13:20.192659Z" PropertyOperation="Initialized"><tt:Source><tt:SimpleItem Name="RelayToken" Value="0"/></tt:Source><tt:Key></tt:Key><tt:Data><tt:SimpleItem Name="LogicalState" Value="inactive"/></tt:Data></tt:Message></wsnt:Message></wsnt:NotificationMessage></tt:Event></tt:MetadataStream>\n'
RELAY_1_INIT = b'<?xml version="1.0" encoding="UTF-8"?>\n<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">\n<tt:Event><wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics" xmlns:tnsaxis="http://www.axis.com/2009/event/topics" xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2" xmlns:wsa5="http://www.w3.org/2005/08/addressing"><wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">tns1:Device/Trigger/Relay</wsnt:Topic><wsnt:ProducerReference><wsa5:Address>uri://4205c5dc-6132-44ad-9aa5-52172e062d2b/ProducerReference</wsa5:Address></wsnt:ProducerReference><wsnt:Message><tt:Message UtcTime="2019-04-22T20:13:20.192659Z" PropertyOperation="Initialized"><tt:Source><tt:SimpleItem Name="RelayToken" Value="1"/></tt:Source><tt:Key></tt:Key><tt:Data><tt:SimpleItem Name="LogicalState" Value="active"/></tt:Data></tt:Message></wsnt:Message></wsnt:NotificationMessage></tt:Event></tt:MetadataStream>\n'


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: {"platform": AXIS_DOMAIN}}
    )

    assert AXIS_DOMAIN not in hass.data


async def test_no_switches(hass):
    """Test that no output events in Axis results in no switch entities."""
    await setup_axis_integration(hass)

    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)


async def test_switches_with_port_cgi(hass, mock_axis_rtspclient):
    """Test that switches are loaded properly using port.cgi."""
    config_entry = await setup_axis_integration(hass)
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

    device.api.vapix.ports = {"0": AsyncMock(), "1": AsyncMock()}
    device.api.vapix.ports["0"].name = "Doorbell"
    device.api.vapix.ports["0"].open = AsyncMock()
    device.api.vapix.ports["0"].close = AsyncMock()
    device.api.vapix.ports["1"].name = ""

    mock_axis_rtspclient(data=RELAY_0_INIT)
    mock_axis_rtspclient(data=RELAY_1_INIT)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    relay_1 = hass.states.get(f"{SWITCH_DOMAIN}.{NAME}_relay_1")
    assert relay_1.state == STATE_ON
    assert relay_1.name == f"{NAME} Relay 1"

    entity_id = f"{SWITCH_DOMAIN}.{NAME}_doorbell"

    relay_0 = hass.states.get(entity_id)
    assert relay_0.state == STATE_OFF
    assert relay_0.name == f"{NAME} Doorbell"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.api.vapix.ports["0"].close.assert_called_once()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.api.vapix.ports["0"].open.assert_called_once()


async def test_switches_with_port_management(hass, mock_axis_rtspclient):
    """Test that switches are loaded properly using port management."""
    api_discovery = deepcopy(API_DISCOVERY_RESPONSE)
    api_discovery["data"]["apiList"].append(API_DISCOVERY_PORT_MANAGEMENT)

    with patch.dict(API_DISCOVERY_RESPONSE, api_discovery):
        config_entry = await setup_axis_integration(hass)
        device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

    device.api.vapix.ports = {"0": AsyncMock(), "1": AsyncMock()}
    device.api.vapix.ports["0"].name = "Doorbell"
    device.api.vapix.ports["0"].open = AsyncMock()
    device.api.vapix.ports["0"].close = AsyncMock()
    device.api.vapix.ports["1"].name = ""

    mock_axis_rtspclient(data=RELAY_0_INIT)
    mock_axis_rtspclient(data=RELAY_1_INIT)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    relay_1 = hass.states.get(f"{SWITCH_DOMAIN}.{NAME}_relay_1")
    assert relay_1.state == STATE_ON
    assert relay_1.name == f"{NAME} Relay 1"

    entity_id = f"{SWITCH_DOMAIN}.{NAME}_doorbell"

    relay_0 = hass.states.get(entity_id)
    assert relay_0.state == STATE_OFF
    assert relay_0.name == f"{NAME} Doorbell"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.api.vapix.ports["0"].close.assert_called_once()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.api.vapix.ports["0"].open.assert_called_once()
