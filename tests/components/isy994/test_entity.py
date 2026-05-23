"""Tests for ISY994 entity base classes."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import (
    COMMAND_FRIENDLY_NAME,
    EMPTY_TIME,
    EVENT_PROPS_IGNORED,
    PROTO_INSTEON,
    PROTO_ZWAVE,
)
from pyisy.nodes import Node
from pyisy.programs import Program
import pytest

from homeassistant.components.isy994.entity import (
    ISYAuxControlEntity,
    ISYEntity,
    ISYNodeEntity,
    ISYProgramEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription


def make_node(
    *,
    name: str = "Test Node",
    uuid: str = "test-uuid",
    address: str = "test-address",
    protocol: str = PROTO_INSTEON,
) -> MagicMock:
    """Create a minimal mock node."""
    node = MagicMock(spec=Node)
    node.name = name
    node.isy = MagicMock()
    node.isy.uuid = uuid
    node.address = address
    node.protocol = protocol
    node.status_events = MagicMock()
    node.control_events = MagicMock()
    return node


# ---------------------------------------------------------------------------
# ISYEntity
# ---------------------------------------------------------------------------


def test_isy_entity_init_unique_id_and_name() -> None:
    """unique_id is composed from isy uuid and node address."""
    node = make_node(name="My Light", uuid="abc", address="1.2.3")
    entity = ISYEntity(node)
    assert entity._attr_unique_id == "abc_1.2.3"
    assert entity._attr_name == "My Light"


def test_isy_entity_init_default_device_info() -> None:
    """Default DeviceInfo uses DOMAIN and isy uuid as identifier."""
    node = make_node(uuid="myuuid")
    entity = ISYEntity(node)
    assert entity._attr_device_info is not None
    assert ("isy994", "myuuid") in entity._attr_device_info["identifiers"]


def test_isy_entity_init_custom_device_info() -> None:
    """Custom DeviceInfo is used as-is when provided."""
    node = make_node()
    custom_info = DeviceInfo(identifiers={("other", "custom")})
    entity = ISYEntity(node, device_info=custom_info)
    assert entity._attr_device_info is custom_info


def test_isy_entity_init_handlers_none() -> None:
    """Change and control handlers start as None."""
    node = make_node()
    entity = ISYEntity(node)
    assert entity._change_handler is None
    assert entity._control_handler is None


async def test_isy_entity_added_to_hass_subscribes_status_events() -> None:
    """async_added_to_hass subscribes to status_events."""
    node = make_node()
    del node.control_events  # no control_events attribute
    entity = ISYEntity(node)
    await entity.async_added_to_hass()
    node.status_events.subscribe.assert_called_once_with(entity.async_on_update)


async def test_isy_entity_added_to_hass_subscribes_control_events() -> None:
    """async_added_to_hass also subscribes to control_events when present."""
    node = make_node()
    entity = ISYEntity(node)
    await entity.async_added_to_hass()
    node.control_events.subscribe.assert_called_once_with(entity.async_on_control)


async def test_isy_entity_added_to_hass_skips_control_events_when_absent() -> None:
    """async_added_to_hass does not error when node has no control_events."""
    node = make_node()
    del node.control_events
    entity = ISYEntity(node)
    await entity.async_added_to_hass()
    assert entity._control_handler is None


def test_isy_entity_on_update_writes_state() -> None:
    """async_on_update triggers a HA state write."""
    node = make_node()
    entity = ISYEntity(node)
    entity.async_write_ha_state = MagicMock()
    entity.async_on_update(MagicMock())
    entity.async_write_ha_state.assert_called_once()


def test_isy_entity_on_control_fires_event_and_writes_state() -> None:
    """async_on_control fires isy994_control event and writes state for non-ignored control."""
    node = make_node()
    entity = ISYEntity(node)
    entity.entity_id = "light.test"
    entity.async_write_ha_state = MagicMock()
    mock_hass = MagicMock()
    entity.hass = mock_hass

    event = MagicMock()
    event.control = "OL"  # not in EVENT_PROPS_IGNORED
    event.value = 100
    event.formatted = "100"
    event.uom = "%"
    event.prec = 0

    entity.async_on_control(event)

    mock_hass.bus.async_fire.assert_called_once()
    call_args = mock_hass.bus.async_fire.call_args
    assert call_args[0][0] == "isy994_control"
    fired_data = call_args[0][1]
    assert fired_data["entity_id"] == "light.test"
    assert fired_data["control"] == "OL"
    entity.async_write_ha_state.assert_called_once()


def test_isy_entity_on_control_skips_state_write_for_ignored_control() -> None:
    """async_on_control does not write state for controls in EVENT_PROPS_IGNORED."""
    node = make_node()
    entity = ISYEntity(node)
    entity.entity_id = "light.test"
    entity.async_write_ha_state = MagicMock()
    entity.hass = MagicMock()

    ignored_control = EVENT_PROPS_IGNORED[0]
    event = MagicMock()
    event.control = ignored_control

    entity.async_on_control(event)

    entity.async_write_ha_state.assert_not_called()
    entity.hass.bus.async_fire.assert_called_once()


# ---------------------------------------------------------------------------
# ISYNodeEntity
# ---------------------------------------------------------------------------


def test_isy_node_entity_parent_node_none_sets_has_entity_name() -> None:
    """When parent_node is None, has_entity_name is True and name is None."""
    node = make_node()
    node.parent_node = None
    entity = ISYNodeEntity(node)
    assert entity._attr_has_entity_name is True
    assert entity._attr_name is None


def test_isy_node_entity_parent_node_set_keeps_name() -> None:
    """When parent_node is set, name is kept and has_entity_name stays False."""
    node = make_node(name="My Switch")
    node.parent_node = MagicMock()
    entity = ISYNodeEntity(node)
    assert entity._attr_has_entity_name is False
    assert entity._attr_name == "My Switch"


def test_isy_node_entity_no_parent_node_attr_keeps_name() -> None:
    """When node has no parent_node attribute at all, name is kept."""
    node = make_node(name="My Device")
    del node.parent_node
    entity = ISYNodeEntity(node)
    assert entity._attr_has_entity_name is False
    assert entity._attr_name == "My Device"


def test_isy_node_entity_available_true() -> None:
    """Available returns the node's enabled attribute."""
    node = make_node()
    node.enabled = True
    entity = ISYNodeEntity(node)
    assert entity.available is True


def test_isy_node_entity_available_false() -> None:
    """Available returns False when node is disabled."""
    node = make_node()
    node.enabled = False
    entity = ISYNodeEntity(node)
    assert entity.available is False


def test_isy_node_entity_available_defaults_true_when_missing() -> None:
    """Available defaults to True when node has no enabled attribute."""
    node = make_node()
    del node.enabled
    entity = ISYNodeEntity(node)
    assert entity.available is True


def test_extra_state_attributes_insteon_excludes_aux_props() -> None:
    """Insteon nodes do not include aux_properties in state attributes."""
    mock_prop = MagicMock()
    mock_prop.formatted = "some_value"
    node = make_node(protocol=PROTO_INSTEON)
    node.aux_properties = {"OL": mock_prop}
    node.parent_node = MagicMock()
    del node.group_all_on
    entity = ISYNodeEntity(node)
    attrs = entity.extra_state_attributes
    assert "OL" not in attrs
    assert "on_level" not in attrs


def test_extra_state_attributes_non_insteon_includes_aux_props() -> None:
    """Non-Insteon nodes include aux_properties using friendly names."""
    mock_prop = MagicMock()
    mock_prop.formatted = "Test_Value"
    node = make_node(protocol="zigbee")
    node.aux_properties = {"OL": mock_prop}
    node.parent_node = MagicMock()
    del node.group_all_on
    entity = ISYNodeEntity(node)
    attrs = entity.extra_state_attributes
    friendly = COMMAND_FRIENDLY_NAME.get("OL", "OL")
    assert friendly in attrs
    assert attrs[friendly] == "test_value"


def test_extra_state_attributes_unknown_control_uses_raw_name() -> None:
    """Unknown control keys fall back to the raw name in state attributes."""
    mock_prop = MagicMock()
    mock_prop.formatted = "42"
    node = make_node(protocol="zigbee")
    node.aux_properties = {"UNKNOWN_CTRL": mock_prop}
    node.parent_node = MagicMock()
    del node.group_all_on
    entity = ISYNodeEntity(node)
    attrs = entity.extra_state_attributes
    assert "UNKNOWN_CTRL" in attrs


def test_extra_state_attributes_group_all_on_true() -> None:
    """Group nodes include group_all_on as STATE_ON when True."""
    node = make_node(protocol="group")
    node.group_all_on = True
    del node.aux_properties
    entity = ISYNodeEntity(node)
    attrs = entity.extra_state_attributes
    assert attrs["group_all_on"] == STATE_ON


def test_extra_state_attributes_group_all_on_false() -> None:
    """Group nodes include group_all_on as STATE_OFF when False."""
    node = make_node(protocol="group")
    node.group_all_on = False
    del node.aux_properties
    entity = ISYNodeEntity(node)
    attrs = entity.extra_state_attributes
    assert attrs["group_all_on"] == STATE_OFF


def test_extra_state_attributes_no_group_all_on() -> None:
    """Non-group nodes do not include group_all_on in attributes."""
    node = make_node(protocol=PROTO_INSTEON)
    del node.aux_properties
    del node.group_all_on
    node.parent_node = MagicMock()
    entity = ISYNodeEntity(node)
    attrs = entity.extra_state_attributes
    assert "group_all_on" not in attrs


async def test_async_send_node_command_valid() -> None:
    """Valid node command is called on the underlying node."""
    node = make_node()
    node.query = AsyncMock(return_value=True)
    entity = ISYNodeEntity(node)
    await entity.async_send_node_command("query")
    node.query.assert_called_once()


async def test_async_send_node_command_invalid_raises() -> None:
    """Invalid command (not an attribute on node) raises HomeAssistantError."""
    node = make_node(address="1.2.3")
    # "nonexistent_cmd" is not part of the Node spec so hasattr returns False
    entity = ISYNodeEntity(node)
    entity.entity_id = "light.test"
    with pytest.raises(HomeAssistantError):
        await entity.async_send_node_command("nonexistent_cmd")


async def test_async_send_raw_node_command_calls_send_cmd() -> None:
    """Raw node command calls node.send_cmd with all parameters."""
    node = make_node()
    node.send_cmd = AsyncMock(return_value=True)
    entity = ISYNodeEntity(node)
    await entity.async_send_raw_node_command("DON", 255, "56", {"key": "val"})
    node.send_cmd.assert_called_once_with("DON", 255, "56", {"key": "val"})


async def test_async_send_raw_node_command_no_send_cmd_raises() -> None:
    """Missing send_cmd on node raises HomeAssistantError."""
    node = make_node()
    del node.send_cmd
    entity = ISYNodeEntity(node)
    entity.entity_id = "light.test"
    with pytest.raises(HomeAssistantError):
        await entity.async_send_raw_node_command("DON")


async def test_async_get_zwave_parameter_zwave_node() -> None:
    """Z-Wave node can request a Z-Wave parameter."""
    node = make_node(protocol=PROTO_ZWAVE)
    node.get_zwave_parameter = AsyncMock()
    entity = ISYNodeEntity(node)
    await entity.async_get_zwave_parameter(5)
    node.get_zwave_parameter.assert_called_once_with(5)


async def test_async_get_zwave_parameter_non_zwave_raises() -> None:
    """Non-Z-Wave node raises HomeAssistantError for Z-Wave parameter request."""
    node = make_node(protocol=PROTO_INSTEON)
    entity = ISYNodeEntity(node)
    entity.entity_id = "switch.test"
    with pytest.raises(HomeAssistantError):
        await entity.async_get_zwave_parameter(5)


async def test_async_set_zwave_parameter_zwave_node() -> None:
    """Z-Wave node can set and then re-fetch a Z-Wave parameter."""
    node = make_node(protocol=PROTO_ZWAVE)
    node.set_zwave_parameter = AsyncMock()
    node.get_zwave_parameter = AsyncMock()
    entity = ISYNodeEntity(node)
    await entity.async_set_zwave_parameter(3, 100, 1)
    node.set_zwave_parameter.assert_called_once_with(3, 100, 1)
    node.get_zwave_parameter.assert_called_once_with(3)


async def test_async_set_zwave_parameter_non_zwave_raises() -> None:
    """Non-Z-Wave node raises HomeAssistantError for Z-Wave parameter set."""
    node = make_node(protocol=PROTO_INSTEON)
    entity = ISYNodeEntity(node)
    entity.entity_id = "switch.test"
    with pytest.raises(HomeAssistantError):
        await entity.async_set_zwave_parameter(3, 100, 1)


async def test_async_rename_node() -> None:
    """rename_node calls node.rename with provided name."""
    node = make_node()
    node.rename = AsyncMock()
    entity = ISYNodeEntity(node)
    await entity.async_rename_node("New Name")
    node.rename.assert_called_once_with("New Name")


# ---------------------------------------------------------------------------
# ISYProgramEntity
# ---------------------------------------------------------------------------


def make_program_node(*, name: str = "Program") -> MagicMock:
    """Create a minimal mock program node."""
    node = MagicMock(spec=Program)
    node.name = name
    node.isy = MagicMock()
    node.isy.uuid = "prog-uuid"
    node.address = "prog-addr"
    return node


def test_program_entity_init_stores_name_and_actions() -> None:
    """ISYProgramEntity stores provided name and actions."""
    status = make_program_node()
    actions = MagicMock()
    entity = ISYProgramEntity("My Program", status, actions)
    assert entity._attr_name == "My Program"
    assert entity._actions is actions


def test_program_entity_init_none_actions() -> None:
    """ISYProgramEntity accepts None for actions."""
    status = make_program_node()
    entity = ISYProgramEntity("My Program", status, None)
    assert entity._actions is None


def test_program_entity_extra_attrs_no_actions() -> None:
    """Without actions, only status_ keys appear in state attributes."""
    status = make_program_node()
    status.enabled = True
    status.last_finished = EMPTY_TIME
    status.last_run = EMPTY_TIME
    status.last_update = EMPTY_TIME
    entity = ISYProgramEntity("Prog", status, None)
    attrs = entity.extra_state_attributes
    assert "status_enabled" in attrs
    assert attrs["status_enabled"] is True
    assert "actions_enabled" not in attrs
    assert "status_last_finished" not in attrs
    assert "status_last_run" not in attrs
    assert "status_last_update" not in attrs


def test_program_entity_extra_attrs_with_actions_empty_times() -> None:
    """With actions and all EMPTY_TIME, time keys are omitted."""
    status = make_program_node()
    status.enabled = True
    status.last_finished = EMPTY_TIME
    status.last_run = EMPTY_TIME
    status.last_update = EMPTY_TIME

    actions = MagicMock()
    actions.enabled = False
    actions.last_finished = EMPTY_TIME
    actions.last_run = EMPTY_TIME
    actions.last_update = EMPTY_TIME
    actions.ran_else = False
    actions.ran_then = True
    actions.run_at_startup = False
    actions.running = False

    entity = ISYProgramEntity("Prog", status, actions)
    attrs = entity.extra_state_attributes
    assert attrs["actions_enabled"] is False
    assert "actions_last_finished" not in attrs
    assert "actions_last_run" not in attrs
    assert "actions_last_update" not in attrs
    assert attrs["ran_else"] is False
    assert attrs["ran_then"] is True


def test_program_entity_extra_attrs_with_non_empty_times() -> None:
    """With non-empty timestamps, time keys appear in state attributes."""
    now = datetime(2024, 6, 1, 12, 0, 0)
    status = make_program_node()
    status.enabled = True
    status.last_finished = now
    status.last_run = now
    status.last_update = now

    actions = MagicMock()
    actions.enabled = True
    actions.last_finished = now
    actions.last_run = now
    actions.last_update = now
    actions.ran_else = True
    actions.ran_then = True
    actions.run_at_startup = True
    actions.running = True

    entity = ISYProgramEntity("Prog", status, actions)
    attrs = entity.extra_state_attributes
    assert attrs["actions_last_finished"] == now
    assert attrs["actions_last_run"] == now
    assert attrs["actions_last_update"] == now
    assert attrs["status_last_finished"] == now
    assert attrs["status_last_run"] == now
    assert attrs["status_last_update"] == now


# ---------------------------------------------------------------------------
# ISYAuxControlEntity
# ---------------------------------------------------------------------------


def make_aux_node(*, address: str = "1.2.3", primary_node: str = "1.2.3") -> MagicMock:
    """Create a minimal mock node for ISYAuxControlEntity."""
    node = MagicMock(spec=Node)
    node.name = "Aux Node"
    node.address = address
    node.primary_node = primary_node
    return node


def test_aux_control_entity_primary_node_naming() -> None:
    """Primary node (address == primary_node) uses plain control name, has_entity_name=True."""
    node = make_aux_node(address="1.2.3", primary_node="1.2.3")
    description = EntityDescription(key="ST")
    entity = ISYAuxControlEntity(
        node=node,
        control="ST",
        unique_id="uuid_1.2.3_ST",
        description=description,
        device_info=None,
    )
    assert entity._attr_has_entity_name is True
    assert "Aux Node" not in entity._attr_name


def test_aux_control_entity_child_node_naming() -> None:
    """Child node (address != primary_node) prepends node.name, has_entity_name=False."""
    node = make_aux_node(address="1.2.3.4", primary_node="1.2.3")
    description = EntityDescription(key="ST")
    entity = ISYAuxControlEntity(
        node=node,
        control="ST",
        unique_id="uuid_1.2.3.4_ST",
        description=description,
        device_info=None,
    )
    assert entity._attr_has_entity_name is False
    assert entity._attr_name.startswith("Aux Node")


def test_aux_control_entity_init_handlers_none() -> None:
    """Change and availability handlers start as None."""
    node = make_aux_node()
    description = EntityDescription(key="ST")
    entity = ISYAuxControlEntity(
        node=node,
        control="ST",
        unique_id="uuid_1.2.3_ST",
        description=description,
        device_info=None,
    )
    assert entity._change_handler is None
    assert entity._availability_handler is None


def test_aux_control_entity_available() -> None:
    """Available reflects node.enabled."""
    node = make_aux_node()
    node.enabled = True
    description = EntityDescription(key="ST")
    entity = ISYAuxControlEntity(
        node=node,
        control="ST",
        unique_id="uuid_1.2.3_ST",
        description=description,
        device_info=None,
    )
    assert entity.available is True
    node.enabled = False
    assert entity.available is False


def test_aux_control_entity_unique_id_and_device_info() -> None:
    """unique_id and device_info are stored from constructor arguments."""
    node = make_aux_node()
    device_info = DeviceInfo(identifiers={("isy994", "myuuid")})
    description = EntityDescription(key="OL")
    entity = ISYAuxControlEntity(
        node=node,
        control="OL",
        unique_id="custom-unique-id",
        description=description,
        device_info=device_info,
    )
    assert entity._attr_unique_id == "custom-unique-id"
    assert entity._attr_device_info is device_info
