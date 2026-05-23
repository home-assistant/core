"""Test ISY994 entity base classes."""

from unittest.mock import MagicMock

from homeassistant.components.isy994.entity import ISYAuxControlEntity, ISYProgramEntity
from homeassistant.components.select import SelectEntityDescription
from homeassistant.const import EntityCategory


def _make_mock_node() -> MagicMock:
    """Return a minimal mock ISY node."""
    node = MagicMock()
    node.name = "Test Node"
    node.isy.uuid = "test-uuid"
    node.address = "test-address"
    node.primary_node = "test-address"
    return node


def _make_mock_status() -> MagicMock:
    """Return a minimal mock ISY program status."""
    status = MagicMock()
    status.name = "Test Program"
    status.isy.uuid = "test-uuid"
    status.address = "test-address"
    return status


def test_program_entity_init_with_none_actions() -> None:
    """Test ISYProgramEntity accepts None for the optional actions parameter."""
    status = _make_mock_status()
    entity = ISYProgramEntity("Test", status, None)
    assert entity._actions is None


def test_aux_control_entity_init_sets_handlers_to_none() -> None:
    """Test ISYAuxControlEntity.__init__ initialises handler attributes to None."""
    node = _make_mock_node()
    description = SelectEntityDescription(
        key="test_key",
        entity_category=EntityCategory.CONFIG,
        options=["a", "b"],
    )
    entity = ISYAuxControlEntity(
        node=node,
        control="ST",
        unique_id="test-uuid_test-address_ST",
        description=description,
        device_info=None,
    )
    assert entity._change_handler is None
    assert entity._availability_handler is None
