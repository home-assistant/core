"""Axis switch platform tests."""

from unittest.mock import call as mock_call, Mock

from homeassistant import config_entries
from homeassistant.components import axis
from homeassistant.setup import async_setup_component

import homeassistant.components.switch as switch

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

ENTRY_CONFIG = {
    axis.CONF_DEVICE: {
        axis.config_flow.CONF_HOST: "1.2.3.4",
        axis.config_flow.CONF_USERNAME: "user",
        axis.config_flow.CONF_PASSWORD: "pass",
        axis.config_flow.CONF_PORT: 80,
    },
    axis.config_flow.CONF_MAC: "1234ABCD",
    axis.config_flow.CONF_MODEL: "model",
    axis.config_flow.CONF_NAME: "model 0",
}

ENTRY_OPTIONS = {
    axis.CONF_CAMERA: False,
    axis.CONF_EVENTS: True,
    axis.CONF_TRIGGER_TIME: 0,
}


async def setup_device(hass):
    """Load the Axis switch platform."""
    from axis import AxisDevice

    loop = Mock()

    config_entry = config_entries.ConfigEntry(
        1,
        axis.DOMAIN,
        "Mock Title",
        ENTRY_CONFIG,
        "test",
        config_entries.CONN_CLASS_LOCAL_PUSH,
        system_options={},
        options=ENTRY_OPTIONS,
    )
    device = axis.AxisNetworkDevice(hass, config_entry)
    device.api = AxisDevice(loop=loop, **config_entry.data[axis.CONF_DEVICE])
    hass.data[axis.DOMAIN] = {device.serial: device}
    device.api.enable_events(event_callback=device.async_event_callback)

    await hass.config_entries.async_forward_entry_setup(config_entry, "switch")
    # To flush out the service call to update the group
    await hass.async_block_till_done()

    return device


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert await async_setup_component(
        hass, switch.DOMAIN, {"switch": {"platform": axis.DOMAIN}}
    )

    assert axis.DOMAIN not in hass.data


async def test_no_switches(hass):
    """Test that no output events in Axis results in no switch entities."""
    await setup_device(hass)

    assert not hass.states.async_entity_ids("switch")


async def test_switches(hass):
    """Test that switches are loaded properly."""
    device = await setup_device(hass)
    device.api.vapix.ports = {"0": Mock(), "1": Mock()}
    device.api.vapix.ports["0"].name = "Doorbell"
    device.api.vapix.ports["1"].name = ""

    for event in EVENTS:
        device.api.stream.event.manage_event(event)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    relay_0 = hass.states.get("switch.model_0_doorbell")
    assert relay_0.state == "off"
    assert relay_0.name == "model 0 Doorbell"

    relay_1 = hass.states.get("switch.model_0_relay_1")
    assert relay_1.state == "on"
    assert relay_1.name == "model 0 Relay 1"

    device.api.vapix.ports["0"].action = Mock()

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.model_0_doorbell"}, blocking=True
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.model_0_doorbell"}, blocking=True
    )

    assert device.api.vapix.ports["0"].action.call_args_list == [
        mock_call("/"),
        mock_call("\\"),
    ]
