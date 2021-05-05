"""Test Rako Utils."""

from homeassistant.components.rako.util import create_unique_id

from tests.components.rako import MOCK_BRIDGE_MAC


def test_create_unique_id():
    """Test creating unique id."""
    assert f"b:{MOCK_BRIDGE_MAC}r:1c:1" == create_unique_id(MOCK_BRIDGE_MAC, 1, 1)
