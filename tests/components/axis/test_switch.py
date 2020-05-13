"""Axis switch platform tests."""

from homeassistant.components import axis
import homeassistant.components.switch as switch
from homeassistant.setup import async_setup_component

from .test_device import NAME, setup_axis_integration

from tests.async_mock import Mock, call as mock_call

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
        hass, switch.DOMAIN, {"switch": {"platform": axis.DOMAIN}}
    )

    assert axis.DOMAIN not in hass.data


async def test_no_switches(hass):
    """Test that no output events in Axis results in no switch entities."""
    await setup_axis_integration(hass)

    assert not hass.states.async_entity_ids("switch")


async def test_switches(hass):
    """Test that switches are loaded properly."""
    device = await setup_axis_integration(hass)

    device.api.vapix.ports = {"0": Mock(), "1": Mock()}
    device.api.vapix.ports["0"].name = "Doorbell"
    device.api.vapix.ports["1"].name = ""

    for event in EVENTS:
        device.api.stream.event.manage_event(event)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("switch")) == 2

    relay_0 = hass.states.get(f"switch.{NAME}_doorbell")
    assert relay_0.state == "off"
    assert relay_0.name == f"{NAME} Doorbell"

    relay_1 = hass.states.get(f"switch.{NAME}_relay_1")
    assert relay_1.state == "on"
    assert relay_1.name == f"{NAME} Relay 1"

    device.api.vapix.ports["0"].action = Mock()

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": f"switch.{NAME}_doorbell"}, blocking=True
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": f"switch.{NAME}_doorbell"}, blocking=True
    )

    assert device.api.vapix.ports["0"].action.call_args_list == [
        mock_call("/"),
        mock_call("\\"),
    ]
