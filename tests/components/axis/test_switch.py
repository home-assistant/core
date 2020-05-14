"""Axis switch platform tests."""

from axis.port_cgi import ACTION_HIGH, ACTION_LOW

from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
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
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: {"platform": AXIS_DOMAIN}}
    )

    assert AXIS_DOMAIN not in hass.data


async def test_no_switches(hass):
    """Test that no output events in Axis results in no switch entities."""
    await setup_axis_integration(hass)

    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)


async def test_switches(hass):
    """Test that switches are loaded properly."""
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

    device.api.vapix.ports["0"].action = Mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": f"switch.{NAME}_doorbell"},
        blocking=True,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": f"switch.{NAME}_doorbell"},
        blocking=True,
    )

    assert device.api.vapix.ports["0"].action.call_args_list == [
        mock_call(ACTION_HIGH),
        mock_call(ACTION_LOW),
    ]
