"""Tests for ISY994 binary sensor platform."""

from unittest.mock import MagicMock, patch

from pyisy.constants import (
    CMD_OFF,
    CMD_ON,
    ISY_VALUE_UNKNOWN,
    PROTO_INSTEON,
    PROTO_ZWAVE,
)
from pyisy.helpers import NodeProperty
from pyisy.nodes import Group, Node
from pyisy.programs import Program
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.isy994.binary_sensor import (
    ISYBinarySensorEntity,
    ISYBinarySensorHeartbeat,
    ISYBinarySensorProgramEntity,
    ISYInsteonBinarySensorEntity,
    _detect_device_type_and_class,
)


def make_node(
    status: object = 0,
    protocol: str = PROTO_INSTEON,
    node_type: str = "1.0.",
    zwave_category: str | None = None,
) -> MagicMock:
    """Return a minimal mock Node."""
    node = MagicMock(spec=Node)
    node.status = status
    node.protocol = protocol
    node.type = node_type
    node.address = "1 1"
    node.primary_node = "1 1"
    node.isy = MagicMock()
    node.isy.uuid = "test-uuid"
    node.status_events = MagicMock()
    node.status_events.subscribe.return_value = MagicMock()
    node.control_events = MagicMock()
    node.control_events.subscribe.return_value = MagicMock()
    if zwave_category is not None:
        node.zwave_props = MagicMock()
        node.zwave_props.category = zwave_category
    return node


def make_program(status: object = 0) -> MagicMock:
    """Return a minimal mock Program."""
    prog = MagicMock(spec=Program)
    prog.status = status
    prog.address = "0001"
    prog.status_events = MagicMock()
    prog.status_events.subscribe.return_value = MagicMock()
    return prog


def make_basic_entity(
    node: MagicMock | None = None,
    device_class: BinarySensorDeviceClass | None = None,
) -> ISYBinarySensorEntity:
    """Return an ISYBinarySensorEntity with node injected."""
    entity = ISYBinarySensorEntity.__new__(ISYBinarySensorEntity)
    entity._node = node or make_node()
    entity._attrs = {}
    entity._attr_device_class = device_class
    return entity


def make_insteon_entity(
    node: MagicMock | None = None,
    computed_state: bool | None = False,
    status_was_unknown: bool = False,
    device_class: BinarySensorDeviceClass | None = None,
) -> ISYInsteonBinarySensorEntity:
    """Return an ISYInsteonBinarySensorEntity with attributes injected."""
    entity = ISYInsteonBinarySensorEntity.__new__(ISYInsteonBinarySensorEntity)
    entity._node = node or make_node()
    entity._attrs = {}
    entity._computed_state = computed_state
    entity._status_was_unknown = status_was_unknown
    entity._negative_node = None
    entity._heartbeat_device = None
    entity._attr_device_class = device_class
    entity.async_write_ha_state = MagicMock()
    entity._attr_name = "Test Sensor"
    return entity


def make_heartbeat_entity(
    parent: MagicMock | None = None,
    computed_state: bool | None = False,
) -> ISYBinarySensorHeartbeat:
    """Return an ISYBinarySensorHeartbeat with attributes injected."""
    node = make_node()
    entity = ISYBinarySensorHeartbeat.__new__(ISYBinarySensorHeartbeat)
    entity._node = node
    entity._attrs = {}
    entity._parent_device = parent or MagicMock()
    entity._heartbeat_timer = None
    entity._computed_state = computed_state
    entity.async_write_ha_state = MagicMock()
    entity.hass = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# _detect_device_type_and_class
# ---------------------------------------------------------------------------


def test_detect_no_type_attribute() -> None:
    """Returns (None, None) when the node has no type attribute."""
    node = MagicMock(spec=Group)
    del node.type
    result = _detect_device_type_and_class(node)
    assert result == (None, None)


def test_detect_zwave_known_category() -> None:
    """Returns correct device_class for a Z-Wave node with a known category."""
    node = make_node(protocol=PROTO_ZWAVE, zwave_category="155")
    device_class, device_type = _detect_device_type_and_class(node)
    assert device_class is BinarySensorDeviceClass.MOTION
    assert device_type == "Z155"


def test_detect_zwave_unknown_category() -> None:
    """Returns (None, device_type) for a Z-Wave node with an unknown category."""
    node = make_node(protocol=PROTO_ZWAVE, zwave_category="999")
    device_class, device_type = _detect_device_type_and_class(node)
    assert device_class is None
    assert device_type == "Z999"


def test_detect_insteon_moisture() -> None:
    """Returns MOISTURE device_class for a matching Insteon node type."""
    node = make_node(protocol=PROTO_INSTEON, node_type="16.8.0.0")
    device_class, _device_type = _detect_device_type_and_class(node)
    assert device_class is BinarySensorDeviceClass.MOISTURE


def test_detect_insteon_motion() -> None:
    """Returns MOTION device_class for a matching Insteon node type."""
    node = make_node(protocol=PROTO_INSTEON, node_type="16.1.0.0")
    device_class, _device_type = _detect_device_type_and_class(node)
    assert device_class is BinarySensorDeviceClass.MOTION


def test_detect_insteon_no_match() -> None:
    """Returns (None, device_type) for Insteon nodes with no matching type."""
    node = make_node(protocol=PROTO_INSTEON, node_type="1.0.0.0")
    device_class, device_type = _detect_device_type_and_class(node)
    assert device_class is None
    assert device_type == "1.0.0.0"


# ---------------------------------------------------------------------------
# ISYBinarySensorEntity.is_on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(ISY_VALUE_UNKNOWN, None, id="unknown"),
        pytest.param(0, False, id="off"),
        pytest.param(255, True, id="on"),
    ],
)
def test_basic_sensor_is_on(status: object, expected: bool | None) -> None:
    """is_on returns None for unknown, False for 0, True for nonzero."""
    entity = make_basic_entity(node=make_node(status=status))
    assert entity.is_on is expected


# ---------------------------------------------------------------------------
# ISYInsteonBinarySensorEntity.is_on  (with inversion logic)
# ---------------------------------------------------------------------------


def test_insteon_sensor_is_on_none_computed_state() -> None:
    """is_on is None when _computed_state is None."""
    entity = make_insteon_entity(computed_state=None)
    assert entity.is_on is None


@pytest.mark.parametrize(
    "device_class",
    [BinarySensorDeviceClass.MOISTURE, BinarySensorDeviceClass.LIGHT],
)
def test_insteon_sensor_is_on_inverted_for_moisture_and_light(
    device_class: BinarySensorDeviceClass,
) -> None:
    """is_on inverts _computed_state for MOISTURE and LIGHT device classes."""
    entity = make_insteon_entity(computed_state=True, device_class=device_class)
    assert entity.is_on is False
    entity._computed_state = False
    assert entity.is_on is True


def test_insteon_sensor_is_on_not_inverted_for_other_classes() -> None:
    """is_on returns _computed_state directly for other device classes."""
    entity = make_insteon_entity(
        computed_state=True, device_class=BinarySensorDeviceClass.MOTION
    )
    assert entity.is_on is True


# ---------------------------------------------------------------------------
# ISYInsteonBinarySensorEntity — init computed_state
# ---------------------------------------------------------------------------


def test_insteon_init_unknown_status_uses_unknown_state() -> None:
    """__init__ sets _computed_state from unknown_state when status is unknown."""
    node = make_node(status=ISY_VALUE_UNKNOWN)
    entity = ISYInsteonBinarySensorEntity(node, unknown_state=False)
    assert entity._computed_state is False
    assert entity._status_was_unknown is True


def test_insteon_init_known_status_sets_computed_state() -> None:
    """__init__ sets _computed_state from node.status when status is known."""
    node = make_node(status=255)
    entity = ISYInsteonBinarySensorEntity(node)
    assert entity._computed_state is True
    assert entity._status_was_unknown is False


# ---------------------------------------------------------------------------
# ISYInsteonBinarySensorEntity.add_negative_node
# ---------------------------------------------------------------------------


def test_add_negative_node_sets_node() -> None:
    """add_negative_node registers the child node."""
    entity = make_insteon_entity()
    child = make_node(status=ISY_VALUE_UNKNOWN)
    entity.add_negative_node(child)
    assert entity._negative_node is child


def test_add_negative_node_agreeing_states_clears_computed() -> None:
    """add_negative_node sets _computed_state to None when both nodes agree."""
    node = make_node(status=255)
    entity = make_insteon_entity(node=node, computed_state=True)
    child = make_node(status=255)
    entity.add_negative_node(child)
    assert entity._computed_state is None


def test_add_negative_node_disagreeing_states_unchanged() -> None:
    """add_negative_node leaves _computed_state unchanged when nodes disagree."""
    node = make_node(status=255)
    entity = make_insteon_entity(node=node, computed_state=True)
    child = make_node(status=0)
    entity.add_negative_node(child)
    assert entity._computed_state is True


# ---------------------------------------------------------------------------
# ISYInsteonBinarySensorEntity — control event handlers
# ---------------------------------------------------------------------------


def test_positive_node_cmd_on_sets_true() -> None:
    """_async_positive_node_control_handler sets True on CMD_ON."""
    entity = make_insteon_entity(computed_state=False)
    event = MagicMock(spec=NodeProperty)
    event.control = CMD_ON
    entity._async_positive_node_control_handler(event)
    assert entity._computed_state is True
    entity.async_write_ha_state.assert_called_once()


def test_positive_node_cmd_off_sets_false() -> None:
    """_async_positive_node_control_handler sets False on CMD_OFF."""
    entity = make_insteon_entity(computed_state=True)
    event = MagicMock(spec=NodeProperty)
    event.control = CMD_OFF
    entity._async_positive_node_control_handler(event)
    assert entity._computed_state is False
    entity.async_write_ha_state.assert_called_once()


def test_positive_node_other_command_no_change() -> None:
    """_async_positive_node_control_handler ignores unrecognised commands."""
    entity = make_insteon_entity(computed_state=True)
    event = MagicMock(spec=NodeProperty)
    event.control = "OTHER"
    entity._async_positive_node_control_handler(event)
    assert entity._computed_state is True
    entity.async_write_ha_state.assert_not_called()


def test_negative_node_cmd_on_sets_false() -> None:
    """_async_negative_node_control_handler sets False (off) on CMD_ON."""
    entity = make_insteon_entity(computed_state=True)
    event = MagicMock(spec=NodeProperty)
    event.control = CMD_ON
    entity._async_negative_node_control_handler(event)
    assert entity._computed_state is False
    entity.async_write_ha_state.assert_called_once()


def test_negative_node_other_command_no_change() -> None:
    """_async_negative_node_control_handler ignores non-CMD_ON events."""
    entity = make_insteon_entity(computed_state=True)
    event = MagicMock(spec=NodeProperty)
    event.control = CMD_OFF
    entity._async_negative_node_control_handler(event)
    assert entity._computed_state is True
    entity.async_write_ha_state.assert_not_called()


# ---------------------------------------------------------------------------
# ISYInsteonBinarySensorEntity.async_on_update
# ---------------------------------------------------------------------------


def test_insteon_on_update_resolves_unknown_state() -> None:
    """async_on_update resolves None computed_state when status_was_unknown."""
    node = make_node(status=255)
    entity = make_insteon_entity(
        node=node, computed_state=None, status_was_unknown=True
    )
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event)
    assert entity._computed_state is True
    assert entity._status_was_unknown is False
    entity.async_write_ha_state.assert_called_once()


def test_insteon_on_update_ignores_when_not_unknown() -> None:
    """async_on_update does nothing when _status_was_unknown is False."""
    entity = make_insteon_entity(computed_state=True, status_was_unknown=False)
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event)
    entity.async_write_ha_state.assert_not_called()


def test_insteon_on_update_ignores_when_computed_not_none() -> None:
    """async_on_update does nothing when _computed_state is already set."""
    entity = make_insteon_entity(computed_state=False, status_was_unknown=True)
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event)
    entity.async_write_ha_state.assert_not_called()


# ---------------------------------------------------------------------------
# ISYInsteonBinarySensorEntity — heartbeat device
# ---------------------------------------------------------------------------


def test_add_heartbeat_device_registers() -> None:
    """add_heartbeat_device stores the heartbeat entity."""
    entity = make_insteon_entity()
    hb = MagicMock()
    entity.add_heartbeat_device(hb)
    assert entity._heartbeat_device is hb


def test_async_heartbeat_calls_device() -> None:
    """_async_heartbeat forwards to the heartbeat device."""
    entity = make_insteon_entity()
    hb = MagicMock()
    entity._heartbeat_device = hb
    entity._async_heartbeat()
    hb.async_heartbeat.assert_called_once()


def test_async_heartbeat_no_device_is_noop() -> None:
    """_async_heartbeat is a no-op when no heartbeat device is registered."""
    entity = make_insteon_entity()
    entity._async_heartbeat()  # should not raise


# ---------------------------------------------------------------------------
# ISYBinarySensorHeartbeat.is_on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("computed_state", "expected"),
    [
        pytest.param(True, True, id="battery_low"),
        pytest.param(False, False, id="battery_ok"),
        pytest.param(None, False, id="unknown_is_false"),
    ],
)
def test_heartbeat_is_on(computed_state: bool | None, expected: bool) -> None:
    """is_on returns bool(_computed_state), so None → False."""
    entity = make_heartbeat_entity(computed_state=computed_state)
    assert entity.is_on is expected


# ---------------------------------------------------------------------------
# ISYBinarySensorHeartbeat.async_heartbeat
# ---------------------------------------------------------------------------


def test_heartbeat_async_heartbeat_sets_ok() -> None:
    """async_heartbeat sets _computed_state to False and writes state."""
    with patch(
        "homeassistant.components.isy994.binary_sensor.async_call_later"
    ) as mock_call_later:
        mock_call_later.return_value = MagicMock()
        entity = make_heartbeat_entity(computed_state=True)
        entity.async_heartbeat()
    assert entity._computed_state is False
    entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# ISYBinarySensorHeartbeat._heartbeat_node_control_handler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("control", [CMD_ON, CMD_OFF])
def test_heartbeat_node_handler_beats_on_on_off(control: str) -> None:
    """_heartbeat_node_control_handler calls async_heartbeat for CMD_ON and CMD_OFF."""
    with patch(
        "homeassistant.components.isy994.binary_sensor.async_call_later"
    ) as mock_call_later:
        mock_call_later.return_value = MagicMock()
        entity = make_heartbeat_entity()
        event = MagicMock(spec=NodeProperty)
        event.control = control
        entity._heartbeat_node_control_handler(event)
    assert entity._computed_state is False


def test_heartbeat_node_handler_ignores_other_commands() -> None:
    """_heartbeat_node_control_handler ignores events that are not CMD_ON or CMD_OFF."""
    entity = make_heartbeat_entity(computed_state=True)
    event = MagicMock(spec=NodeProperty)
    event.control = "OTHER"
    entity._heartbeat_node_control_handler(event)
    assert entity._computed_state is True
    entity.async_write_ha_state.assert_not_called()


# ---------------------------------------------------------------------------
# ISYBinarySensorHeartbeat.async_on_update
# ---------------------------------------------------------------------------


def test_heartbeat_on_update_is_noop() -> None:
    """async_on_update does nothing (heartbeat listens to control events only)."""
    entity = make_heartbeat_entity(computed_state=True)
    entity.async_on_update(MagicMock())
    entity.async_write_ha_state.assert_not_called()


# ---------------------------------------------------------------------------
# ISYBinarySensorHeartbeat.extra_state_attributes
# ---------------------------------------------------------------------------


def test_heartbeat_extra_state_attributes_has_parent_entity_id() -> None:
    """extra_state_attributes includes parent_entity_id."""
    parent = MagicMock()
    parent.entity_id = "binary_sensor.parent"
    entity = make_heartbeat_entity(parent=parent)
    attrs = entity.extra_state_attributes
    assert attrs["parent_entity_id"] == "binary_sensor.parent"


# ---------------------------------------------------------------------------
# ISYBinarySensorProgramEntity.is_on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(0, False, id="off"),
        pytest.param(1, True, id="on"),
    ],
)
def test_program_sensor_is_on(status: object, expected: bool) -> None:
    """is_on returns bool(program status)."""
    entity = ISYBinarySensorProgramEntity.__new__(ISYBinarySensorProgramEntity)
    entity._node = make_program(status=status)
    assert entity.is_on is expected
