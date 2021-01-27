"""Test Rako Utils."""
from homeassistant.components.rako.util import create_unique_id

from . import MOCK_MAC


def test_create_unique_id():
    """Test creating unique id."""
    assert f"b:{MOCK_MAC}r:1c:1" == create_unique_id(MOCK_MAC, 1, 1)
