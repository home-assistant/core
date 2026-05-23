"""Test ISY994 entity base classes."""

from unittest.mock import MagicMock

import pytest
from pyisy.constants import PROTO_INSTEON, PROTO_ZWAVE

from homeassistant.components.isy994.entity import ISYNodeEntity


@pytest.mark.parametrize(
    ("protocol", "expected_in_attrs"),
    [
        pytest.param(PROTO_INSTEON, False, id="insteon_excluded"),
        pytest.param(PROTO_ZWAVE, False, id="zwave_excluded"),
        pytest.param("zigbee", True, id="other_included"),
    ],
)
def test_extra_state_attributes_aux_properties_by_protocol(
    protocol: str,
    expected_in_attrs: bool,
) -> None:
    """Test that aux_properties are excluded for Insteon and Z-Wave nodes."""
    mock_prop = MagicMock()
    mock_prop.formatted = "test_value"

    node = MagicMock()
    node.name = "Test Node"
    node.isy.uuid = "test-uuid"
    node.address = "test-address"
    node.protocol = protocol
    node.aux_properties = {"FAKE_PROP": mock_prop}
    node.parent_node = MagicMock()  # not None, so has_entity_name stays False

    entity = ISYNodeEntity(node)
    attrs = entity.extra_state_attributes

    assert ("FAKE_PROP" in attrs) == expected_in_attrs
