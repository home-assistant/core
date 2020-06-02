"""Axis switch platform tests."""

from copy import deepcopy

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.setup import async_setup_component

from .test_device import (
    API_DISCOVERY_PORT_MANAGEMENT,
    API_DISCOVERY_RESPONSE,
    NAME,
    setup_axis_integration,
)

from tests.async_mock import Mock, patch

EVENTS = [
    {
        "operation": "Initialized",
        "topic": "tns1:Device/Trigger/Relay",
        "source": "RelayToken",
        "source_idx": "0",
        "type": "LogicalState",
        "value": "inactive",
    },
    {
        "operation": "Initialized",
        "topic": "tns1:Device/Trigger/Relay",
        "source": "RelayToken",
        "source_idx": "1",
        "type": "LogicalState",
        "value": "active",
    },
]


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


async def test_switches_with_port_cgi(hass):
    """Test that switches are loaded properly using port.cgi."""
    device = await setup_axis_integration(hass)

    device.api.vapix.ports = {"0": Mock(), "1": Mock()}
    device.api.vapix.ports["0"].name = "Doorbell"
    device.api.vapix.ports["1"].name = ""

    for event in EVENTS:
        device.api.event.process_event(event)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    relay_0 = hass.states.get(f"switch.{NAME}_doorbell")
    assert relay_0.state == "off"
    assert relay_0.name == f"{NAME} Doorbell"

    relay_1 = hass.states.get(f"switch.{NAME}_relay_1")
    assert relay_1.state == "on"
    assert relay_1.name == f"{NAME} Relay 1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": f"switch.{NAME}_doorbell"},
        blocking=True,
    )
    device.api.vapix.ports["0"].close.assert_called_once()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": f"switch.{NAME}_doorbell"},
        blocking=True,
    )
    device.api.vapix.ports["0"].open.assert_called_once()


async def test_switches_with_port_management(hass):
    """Test that switches are loaded properly using port management."""
    api_discovery = deepcopy(API_DISCOVERY_RESPONSE)
    api_discovery["data"]["apiList"].append(API_DISCOVERY_PORT_MANAGEMENT)

    with patch.dict(API_DISCOVERY_RESPONSE, api_discovery):
        device = await setup_axis_integration(hass)

    device.api.vapix.ports = {"0": Mock(), "1": Mock()}
    device.api.vapix.ports["0"].name = "Doorbell"
    device.api.vapix.ports["1"].name = ""

    for event in EVENTS:
        device.api.event.process_event(event)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    relay_0 = hass.states.get(f"switch.{NAME}_doorbell")
    assert relay_0.state == "off"
    assert relay_0.name == f"{NAME} Doorbell"

    relay_1 = hass.states.get(f"switch.{NAME}_relay_1")
    assert relay_1.state == "on"
    assert relay_1.name == f"{NAME} Relay 1"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": f"switch.{NAME}_doorbell"},
        blocking=True,
    )
    device.api.vapix.ports["0"].close.assert_called_once()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": f"switch.{NAME}_doorbell"},
        blocking=True,
    )
    device.api.vapix.ports["0"].open.assert_called_once()
