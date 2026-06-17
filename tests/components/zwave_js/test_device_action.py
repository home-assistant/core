"""The tests for Z-Wave JS device actions."""

from unittest.mock import patch

import pytest
import voluptuous_serialize
from zwave_js_server.client import Client
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.zwave_js import DOMAIN, device_action
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations


async def test_get_actions(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected actions from a zwave_js node."""
    node = lock_schlage_be469
    driver = client.driver
    assert driver
    device = device_registry.async_get_device(identifiers={get_device_id(driver, node)})
    assert device
    binary_sensor = entity_registry.async_get(
        "binary_sensor.touchscreen_deadbolt_low_battery_level"
    )
    assert binary_sensor
    lock = entity_registry.async_get("lock.touchscreen_deadbolt")
    assert lock
    expected_actions = [
        {
            "domain": DOMAIN,
            "type": "clear_lock_usercode",
            "device_id": device.id,
            "entity_id": lock.id,
            "metadata": {"secondary": False},
        },
        {
            "domain": DOMAIN,
            "type": "set_lock_usercode",
            "device_id": device.id,
            "entity_id": lock.id,
            "metadata": {"secondary": False},
        },
        {
            "domain": DOMAIN,
            "type": "refresh_value",
            "device_id": device.id,
            "entity_id": binary_sensor.id,
            "metadata": {"secondary": True},
        },
        {
            "domain": DOMAIN,
            "type": "refresh_value",
            "device_id": device.id,
            "entity_id": lock.id,
            "metadata": {"secondary": False},
        },
        {
            "domain": DOMAIN,
            "type": "set_value",
            "device_id": device.id,
            "metadata": {},
        },
        {
            "domain": DOMAIN,
            "type": "ping",
            "device_id": device.id,
            "metadata": {},
        },
        {
            "domain": DOMAIN,
            "type": "set_config_parameter",
            "device_id": device.id,
            "endpoint": 0,
            "parameter": 3,
            "bitmask": None,
            "subtype": "3 (Beeper) on endpoint 0",
            "metadata": {},
        },
    ]
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device.id
    )
    for action in expected_actions:
        assert action in actions

    # Test that we don't return actions for a controller node
    device = device_registry.async_get_device(
        identifiers={get_device_id(driver, client.driver.controller.nodes[1])}
    )
    assert device
    assert (
        await async_get_device_automations(hass, DeviceAutomationType.ACTION, device.id)
        == []
    )


async def test_get_actions_meter(
    hass: HomeAssistant,
    client: Client,
    aeon_smart_switch_6: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected meter actions from a zwave_js node."""
    node = aeon_smart_switch_6
    driver = client.driver
    assert driver
    device = device_registry.async_get_device(identifiers={get_device_id(driver, node)})
    assert device
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device.id
    )
    filtered_actions = [action for action in actions if action["type"] == "reset_meter"]
    assert len(filtered_actions) > 0


async def test_actions(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test actions."""
    node = climate_radio_thermostat_ct100_plus
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device(identifiers={device_id})
    assert device

    climate = entity_registry.async_get("climate.z_wave_thermostat")
    assert climate

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_refresh_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "refresh_value",
                        "device_id": device.id,
                        "entity_id": climate.id,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_ping",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "ping",
                        "device_id": device.id,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_value",
                        "device_id": device.id,
                        "command_class": 112,
                        "property": 1,
                        "value": 1,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_config_parameter",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_config_parameter",
                        "device_id": device.id,
                        "endpoint": 0,
                        "parameter": 1,
                        "bitmask": None,
                        "subtype": "3 (Beeper)",
                        "value": 1,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_config_parameter_no_endpoint",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_config_parameter",
                        "device_id": device.id,
                        "parameter": 1,
                        "bitmask": None,
                        "subtype": "3 (Beeper)",
                        "value": 1,
                    },
                },
            ]
        },
    )

    with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
        hass.bus.async_fire("test_event_refresh_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 1
        assert args[0].value_id == "13-64-1-mode"

    # Call action a second time to confirm that it works (this was previously a bug)
    with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
        hass.bus.async_fire("test_event_refresh_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 1
        assert args[0].value_id == "13-64-1-mode"

    with patch("zwave_js_server.model.node.Node.async_ping") as mock_call:
        hass.bus.async_fire("test_event_ping")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 0

    with patch("zwave_js_server.model.node.Node.async_set_value") as mock_call:
        hass.bus.async_fire("test_event_set_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0] == "13-112-0-1"
        assert args[1] == 1

    with patch(
        "homeassistant.components.zwave_js.services.async_set_config_parameter"
    ) as mock_call:
        hass.bus.async_fire("test_event_set_config_parameter")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 3
        assert args[0].node_id == 13
        assert args[1] == 1
        assert args[2] == 1

    with patch(
        "homeassistant.components.zwave_js.services.async_set_config_parameter"
    ) as mock_call:
        hass.bus.async_fire("test_event_set_config_parameter_no_endpoint")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 3
        assert args[0].node_id == 13
        assert args[1] == 1
        assert args[2] == 1


async def test_actions_legacy(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test actions."""
    node = climate_radio_thermostat_ct100_plus
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device(identifiers={device_id})
    assert device

    climate = entity_registry.async_get("climate.z_wave_thermostat")
    assert climate

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_refresh_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "refresh_value",
                        "device_id": device.id,
                        "entity_id": climate.entity_id,
                    },
                },
            ]
        },
    )

    with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
        hass.bus.async_fire("test_event_refresh_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 1
        assert args[0].value_id == "13-64-1-mode"

    # Call action a second time to confirm that it works (this was previously a bug)
    with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
        hass.bus.async_fire("test_event_refresh_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 1
        assert args[0].value_id == "13-64-1-mode"


async def test_actions_multiple_calls(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test actions can be called multiple times and still work."""
    node = climate_radio_thermostat_ct100_plus
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device({device_id})
    assert device
    climate = entity_registry.async_get("climate.z_wave_thermostat")
    assert climate

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_refresh_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "refresh_value",
                        "device_id": device.id,
                        "entity_id": climate.id,
                    },
                },
            ]
        },
    )

    # Trigger automation multiple times to confirm that it works each time
    for _ in range(5):
        with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
            hass.bus.async_fire("test_event_refresh_value")
            await hass.async_block_till_done()
            mock_call.assert_called_once()
            args = mock_call.call_args_list[0][0]
            assert len(args) == 1
            assert args[0].value_id == "13-64-1-mode"


async def test_lock_actions(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test actions for locks."""
    node = lock_schlage_be469
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device(identifiers={device_id})
    assert device
    lock = entity_registry.async_get("lock.touchscreen_deadbolt")
    assert lock

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_clear_lock_usercode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "clear_lock_usercode",
                        "device_id": device.id,
                        "entity_id": lock.id,
                        "code_slot": 1,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_lock_usercode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_lock_usercode",
                        "device_id": device.id,
                        "entity_id": lock.id,
                        "code_slot": 1,
                        "usercode": "1234",
                    },
                },
            ]
        },
    )

    with patch("homeassistant.components.zwave_js.lock.clear_usercode") as mock_call:
        hass.bus.async_fire("test_event_clear_lock_usercode")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0].node_id == node.node_id
        assert args[1] == 1

    with patch("homeassistant.components.zwave_js.lock.set_usercode") as mock_call:
        hass.bus.async_fire("test_event_set_lock_usercode")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 3
        assert args[0].node_id == node.node_id
        assert args[1] == 1
        assert args[2] == "1234"


async def test_reset_meter_action(
    hass: HomeAssistant,
    client: Client,
    aeon_smart_switch_6: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reset_meter action."""
    node = aeon_smart_switch_6
    driver = client.driver
    assert driver
    device_id = get_device_id(driver, node)
    device = device_registry.async_get_device(identifiers={device_id})
    assert device
    sensor = entity_registry.async_get("sensor.smart_switch_6_electric_consumed_kwh")
    assert sensor

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_reset_meter",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "reset_meter",
                        "device_id": device.id,
                        "entity_id": sensor.id,
                    },
                },
            ]
        },
    )

    with patch(
        "zwave_js_server.model.endpoint.Endpoint.async_invoke_cc_api"
    ) as mock_call:
        hass.bus.async_fire("test_event_reset_meter")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0] == CommandClass.METER
        assert args[1] == "reset"


@pytest.mark.parametrize(
    "device_endpoint",
    [
        pytest.param(None, id="node_device"),
        pytest.param(1, id="sub_device"),
    ],
)
async def test_set_value_action_endpoint_sub_device(
    hass: HomeAssistant,
    client: Client,
    vision_security_zl7432: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    device_endpoint: int | None,
) -> None:
    """Test set_value action for a value moved to an endpoint sub-device.

    The Binary Switch value on endpoint 1 now lives on an endpoint sub-device. Automations
    created before this change stored the node device_id. Verify the action targets the
    correct endpoint value whether it references the node device_id (backward
    compatibility) or the endpoint sub-device device_id.
    """
    node = vision_security_zl7432
    driver = client.driver
    assert driver
    device = device_registry.async_get_device(
        identifiers={get_device_id(driver, node, device_endpoint)}
    )
    assert device

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_value",
                        "device_id": device.id,
                        "command_class": CommandClass.SWITCH_BINARY.value,
                        "property": "targetValue",
                        "endpoint": 1,
                        "value": True,
                    },
                },
            ]
        },
    )

    with patch("zwave_js_server.model.node.Node.async_set_value") as mock_call:
        hass.bus.async_fire("test_event_set_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0] == "7-37-1-targetValue"
        assert args[1] is True


async def test_reset_meter_action_endpoint_sub_device(
    hass: HomeAssistant,
    client: Client,
    shelly_qnsh_001P10_shutter: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reset_meter action for a meter entity moved to an endpoint sub-device.

    The meter values on endpoints 1 and 2 collide, so the meter sensors now live on
    endpoint sub-devices. An automation created before this change stored the node
    device_id together with the entity registry id. Verify it still executes: the entity
    service resolves by entity_id, which is unchanged by the device move.
    """
    node = shelly_qnsh_001P10_shutter
    driver = client.driver
    assert driver

    node_device = device_registry.async_get_device(
        identifiers={get_device_id(driver, node)}
    )
    assert node_device
    sub_device = device_registry.async_get_device(
        identifiers={get_device_id(driver, node, 1)}
    )
    assert sub_device

    # The meter sensor on endpoint 1 now lives on the endpoint sub-device.
    meter_entity = next(
        entry
        for entry in er.async_entries_for_device(entity_registry, sub_device.id)
        if entry.unique_id.endswith("5-50-1-value-65537")
    )
    assert meter_entity.device_id == sub_device.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_reset_meter",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "reset_meter",
                        # Stored as the node device_id, as it would have been before the
                        # meter entity moved to the endpoint sub-device.
                        "device_id": node_device.id,
                        "entity_id": meter_entity.id,
                    },
                },
            ]
        },
    )

    with patch(
        "zwave_js_server.model.endpoint.Endpoint.async_invoke_cc_api"
    ) as mock_call:
        hass.bus.async_fire("test_event_reset_meter")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0] == CommandClass.METER
        assert args[1] == "reset"


@pytest.mark.parametrize(
    "device_endpoint",
    [
        pytest.param(None, id="node_device"),
        pytest.param(1, id="sub_device"),
    ],
)
async def test_refresh_value_action_endpoint_sub_device(
    hass: HomeAssistant,
    client: Client,
    vision_security_zl7432: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_endpoint: int | None,
) -> None:
    """Test refresh_value action for an entity moved to an endpoint sub-device.

    The switch on endpoint 1 now lives on an endpoint sub-device. An automation created
    before this change stored the node device_id together with the entity registry id.
    Verify it still executes: the entity service resolves by entity_id, which is unchanged
    by the device move.
    """
    node = vision_security_zl7432
    driver = client.driver
    assert driver
    device = device_registry.async_get_device(
        identifiers={get_device_id(driver, node, device_endpoint)}
    )
    assert device

    switch_entity = entity_registry.async_get(
        "switch.in_wall_dual_relay_switch_binary_power_switch_1"
    )
    assert switch_entity

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_refresh_value",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "refresh_value",
                        "device_id": device.id,
                        "entity_id": switch_entity.id,
                    },
                },
            ]
        },
    )

    with patch("zwave_js_server.model.node.Node.async_poll_value") as mock_call:
        hass.bus.async_fire("test_event_refresh_value")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 1
        assert args[0].value_id == "7-37-1-currentValue"


async def test_lock_actions_endpoint_sub_device(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test lock usercode actions remain backwards compatible with the node device.

    Door Lock values are on the root endpoint, so the lock entity is never moved to an
    endpoint sub-device. Confirm the lock stays on the node device and that automations
    created before the sub-device change (storing the node device_id) still execute the
    clear/set lock usercode actions.
    """
    node = lock_schlage_be469
    driver = client.driver
    assert driver
    node_device = device_registry.async_get_device(
        identifiers={get_device_id(driver, node)}
    )
    assert node_device
    lock = entity_registry.async_get("lock.touchscreen_deadbolt")
    assert lock
    assert lock.device_id == node_device.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_clear_lock_usercode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "clear_lock_usercode",
                        "device_id": node_device.id,
                        "entity_id": lock.id,
                        "code_slot": 1,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_lock_usercode",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "type": "set_lock_usercode",
                        "device_id": node_device.id,
                        "entity_id": lock.id,
                        "code_slot": 1,
                        "usercode": "1234",
                    },
                },
            ]
        },
    )

    with patch("homeassistant.components.zwave_js.lock.clear_usercode") as mock_call:
        hass.bus.async_fire("test_event_clear_lock_usercode")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 2
        assert args[0].node_id == node.node_id
        assert args[1] == 1

    with patch("homeassistant.components.zwave_js.lock.set_usercode") as mock_call:
        hass.bus.async_fire("test_event_set_lock_usercode")
        await hass.async_block_till_done()
        mock_call.assert_called_once()
        args = mock_call.call_args_list[0][0]
        assert len(args) == 3
        assert args[0].node_id == node.node_id
        assert args[1] == 1
        assert args[2] == "1234"


async def test_get_actions_endpoint_sub_device(
    hass: HomeAssistant,
    client: Client,
    shelly_qnsh_001P10_shutter: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test how entity actions are listed once entities move to endpoint sub-devices.

    Node-level actions (set_value, ping) remain available from the node device. Entity
    actions for a meter entity that moved to an endpoint sub-device are now listed under
    that sub-device, not under the node device. Existing automations are unaffected since
    they store the entity registry id, but newly created automations list the entity
    action under the sub-device.
    """
    node = shelly_qnsh_001P10_shutter
    driver = client.driver
    assert driver

    node_device = device_registry.async_get_device(
        identifiers={get_device_id(driver, node)}
    )
    assert node_device
    sub_device = device_registry.async_get_device(
        identifiers={get_device_id(driver, node, 1)}
    )
    assert sub_device

    meter_entity = next(
        entry
        for entry in er.async_entries_for_device(entity_registry, sub_device.id)
        if entry.unique_id.endswith("5-50-1-value-65537")
    )

    node_actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, node_device.id
    )
    node_action_types = {action["type"] for action in node_actions}
    assert "set_value" in node_action_types
    assert "ping" in node_action_types
    # The moved meter entity's actions are not listed under the node device.
    assert not any(
        action.get("entity_id") == meter_entity.id for action in node_actions
    )

    sub_actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, sub_device.id
    )
    assert any(
        action["type"] == "reset_meter" and action.get("entity_id") == meter_entity.id
        for action in sub_actions
    )
    assert any(
        action["type"] == "refresh_value" and action.get("entity_id") == meter_entity.id
        for action in sub_actions
    )


async def test_get_action_capabilities(
    hass: HomeAssistant,
    client: Client,
    climate_radio_thermostat_ct100_plus: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we get the expected action capabilities."""
    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, climate_radio_thermostat_ct100_plus)}
    )
    assert device

    # Test refresh_value
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "refresh_value",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "type": "boolean",
            "name": "refresh_all_values",
            "optional": True,
            "required": False,
        }
    ]

    # Test ping
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "ping",
        },
    )
    assert not capabilities

    # Test set_value
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_value",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    cc_options = [
        ("133", "Association"),
        ("89", "Association Group Information"),
        ("128", "Battery"),
        ("129", "Clock"),
        ("112", "Configuration"),
        ("90", "Device Reset Locally"),
        ("122", "Firmware Update Meta Data"),
        ("135", "Indicator"),
        ("114", "Manufacturer Specific"),
        ("96", "Multi Channel"),
        ("142", "Multi Channel Association"),
        ("49", "Multilevel Sensor"),
        ("115", "Powerlevel"),
        ("68", "Thermostat Fan Mode"),
        ("69", "Thermostat Fan State"),
        ("64", "Thermostat Mode"),
        ("66", "Thermostat Operating State"),
        ("67", "Thermostat Setpoint"),
        ("134", "Version"),
        ("94", "Z-Wave Plus Info"),
    ]

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "command_class",
            "required": True,
            "options": cc_options,
            "type": "select",
        },
        {"name": "property", "required": True, "type": "string"},
        {"name": "property_key", "optional": True, "required": False, "type": "string"},
        {"name": "endpoint", "optional": True, "required": False, "type": "string"},
        {"name": "value", "required": True, "type": "string"},
        {
            "type": "boolean",
            "name": "wait_for_result",
            "optional": True,
            "required": False,
        },
    ]

    # Test enumerated type param
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_config_parameter",
            "endpoint": 0,
            "parameter": 1,
            "bitmask": None,
            "subtype": "1 (Temperature Reporting Threshold)",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "value",
            "required": True,
            "options": [
                ("0", "Disabled"),
                ("1", "0.5° F"),
                ("2", "1.0° F"),
                ("3", "1.5° F"),
                ("4", "2.0° F"),
            ],
            "type": "select",
        }
    ]

    # Test range type param
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_config_parameter",
            "endpoint": 0,
            "parameter": 10,
            "bitmask": None,
            "subtype": "10 (Temperature Reporting Filter)",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "value",
            "required": True,
            "type": "integer",
            "valueMin": 0,
            "valueMax": 124,
        }
    ]

    # Test undefined type param
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "type": "set_config_parameter",
            "endpoint": 0,
            "parameter": 2,
            "bitmask": None,
            "subtype": "2 (HVAC Settings)",
        },
    )
    assert not capabilities


async def test_get_action_capabilities_lock_triggers(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected action capabilities for lock triggers."""
    device = dr.async_entries_for_config_entry(device_registry, integration.entry_id)[0]
    lock = entity_registry.async_get("lock.touchscreen_deadbolt")
    assert lock

    # Test clear_lock_usercode
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "entity_id": lock.id,
            "type": "clear_lock_usercode",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"type": "string", "name": "code_slot", "required": True}]

    # Test set_lock_usercode
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "entity_id": lock.id,
            "type": "set_lock_usercode",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {"type": "string", "name": "code_slot", "required": True},
        {"type": "string", "name": "usercode", "required": True},
    ]


async def test_get_action_capabilities_meter_triggers(
    hass: HomeAssistant,
    client: Client,
    aeon_smart_switch_6: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected action capabilities for meter triggers."""
    node = aeon_smart_switch_6
    driver = client.driver
    assert driver
    device = device_registry.async_get_device(identifiers={get_device_id(driver, node)})
    assert device
    capabilities = await device_action.async_get_action_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device.id,
            "entity_id": "123456789",  # The entity is not checked
            "type": "reset_meter",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"type": "string", "name": "value", "optional": True, "required": False}]


async def test_failure_scenarios(
    hass: HomeAssistant,
    client: Client,
    hank_binary_switch: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test failure scenarios."""
    device = dr.async_entries_for_config_entry(device_registry, integration.entry_id)[0]

    with pytest.raises(HomeAssistantError):
        await device_action.async_call_action_from_config(
            hass, {"type": "failed.test", "device_id": device.id}, {}, None
        )

    assert (
        await device_action.async_get_action_capabilities(
            hass, {"type": "failed.test", "device_id": device.id}
        )
        == {}
    )


async def test_unavailable_entity_actions(
    hass: HomeAssistant,
    client: Client,
    lock_schlage_be469: Node,
    integration: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unavailable entities are not included in actions list."""
    entity_id_unavailable = "binary_sensor.touchscreen_deadbolt_low_battery_level"
    hass.states.async_set(entity_id_unavailable, STATE_UNAVAILABLE, force_update=True)
    await hass.async_block_till_done()
    node = lock_schlage_be469
    driver = client.driver
    assert driver
    device = device_registry.async_get_device(identifiers={get_device_id(driver, node)})
    assert device
    binary_sensor = entity_registry.async_get(entity_id_unavailable)
    assert binary_sensor
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device.id
    )
    assert not any(
        action.get("entity_id") == entity_id_unavailable for action in actions
    )
    assert not any(action.get("entity_id") == binary_sensor.id for action in actions)


def test_action_schema_coerces_string_command_class() -> None:
    """Test that SET_VALUE action schema accepts both int and string command_class."""
    for command_class_value in (
        CommandClass.DOOR_LOCK.value,
        str(CommandClass.DOOR_LOCK.value),
    ):
        config = device_action.SET_VALUE_SCHEMA(
            {
                "device_id": "device123",
                "domain": DOMAIN,
                "type": "set_value",
                "command_class": command_class_value,
                "property": "targetMode",
                "value": 255,
            }
        )
        assert config["command_class"] == CommandClass.DOOR_LOCK.value
