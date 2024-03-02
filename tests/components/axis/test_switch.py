"""Axis switch platform tests."""
from unittest.mock import patch

from axis.vapix.models.api import CONTEXT
import pytest

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import API_DISCOVERY_PORT_MANAGEMENT, NAME


async def test_platform_manually_configured(hass: HomeAssistant) -> None:
    """Test that nothing happens when platform is manually configured."""
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: {"platform": AXIS_DOMAIN}}
    )

    assert AXIS_DOMAIN not in hass.data


async def test_no_switches(hass: HomeAssistant, setup_config_entry) -> None:
    """Test that no output events in Axis results in no switch entities."""
    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)


PORT_DATA = """root.IOPort.I0.Configurable=yes
root.IOPort.I0.Direction=output
root.IOPort.I0.Output.Name=Doorbell
root.IOPort.I0.Output.Active=closed
root.IOPort.I1.Configurable=yes
root.IOPort.I1.Direction=output
root.IOPort.I1.Output.Name=
root.IOPort.I1.Output.Active=open
"""


@pytest.mark.parametrize("param_ports_payload", [PORT_DATA])
async def test_switches_with_port_cgi(
    hass: HomeAssistant, setup_config_entry, mock_rtsp_event
) -> None:
    """Test that switches are loaded properly using port.cgi."""
    mock_rtsp_event(
        topic="tns1:Device/Trigger/Relay",
        data_type="LogicalState",
        data_value="inactive",
        source_name="RelayToken",
        source_idx="0",
    )
    mock_rtsp_event(
        topic="tns1:Device/Trigger/Relay",
        data_type="LogicalState",
        data_value="active",
        source_name="RelayToken",
        source_idx="1",
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    relay_1 = hass.states.get(f"{SWITCH_DOMAIN}.{NAME}_relay_1")
    assert relay_1.state == STATE_ON
    assert relay_1.name == f"{NAME} Relay 1"

    entity_id = f"{SWITCH_DOMAIN}.{NAME}_doorbell"

    relay_0 = hass.states.get(entity_id)
    assert relay_0.state == STATE_OFF
    assert relay_0.name == f"{NAME} Doorbell"

    with patch("axis.vapix.vapix.Ports.close") as mock_turn_on:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_turn_on.assert_called_once_with("0")

    with patch("axis.vapix.vapix.Ports.open") as mock_turn_off:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with("0")


PORT_MANAGEMENT_RESPONSE = {
    "apiVersion": "1.0",
    "method": "getPorts",
    "context": CONTEXT,
    "data": {
        "numberOfPorts": 2,
        "items": [
            {
                "port": "0",
                "configurable": True,
                "usage": "",
                "name": "Doorbell",
                "direction": "output",
                "state": "open",
                "normalState": "open",
            },
            {
                "port": "1",
                "configurable": True,
                "usage": "",
                "name": "",
                "direction": "output",
                "state": "open",
                "normalState": "open",
            },
        ],
    },
}


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_PORT_MANAGEMENT])
@pytest.mark.parametrize("port_management_payload", [PORT_MANAGEMENT_RESPONSE])
async def test_switches_with_port_management(
    hass: HomeAssistant, setup_config_entry, mock_rtsp_event
) -> None:
    """Test that switches are loaded properly using port management."""
    mock_rtsp_event(
        topic="tns1:Device/Trigger/Relay",
        data_type="LogicalState",
        data_value="inactive",
        source_name="RelayToken",
        source_idx="0",
    )
    mock_rtsp_event(
        topic="tns1:Device/Trigger/Relay",
        data_type="LogicalState",
        data_value="active",
        source_name="RelayToken",
        source_idx="1",
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    relay_1 = hass.states.get(f"{SWITCH_DOMAIN}.{NAME}_relay_1")
    assert relay_1.state == STATE_ON
    assert relay_1.name == f"{NAME} Relay 1"

    entity_id = f"{SWITCH_DOMAIN}.{NAME}_doorbell"

    relay_0 = hass.states.get(entity_id)
    assert relay_0.state == STATE_OFF
    assert relay_0.name == f"{NAME} Doorbell"

    # State update

    mock_rtsp_event(
        topic="tns1:Device/Trigger/Relay",
        data_type="LogicalState",
        data_value="active",
        source_name="RelayToken",
        source_idx="0",
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{SWITCH_DOMAIN}.{NAME}_relay_1").state == STATE_ON

    with patch("axis.vapix.vapix.IoPortManagement.close") as mock_turn_on:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_turn_on.assert_called_once_with("0")

    with patch("axis.vapix.vapix.IoPortManagement.open") as mock_turn_off:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_turn_off.assert_called_once_with("0")
