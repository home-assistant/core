"""Test Z-Wave JS helpers module."""
import pytest

from homeassistant.components.zwave_js.helpers import ZwaveValueID


async def test_empty_zwave_value_id():
    """Test empty ZwaveValueID is invalid."""
    with pytest.raises(ValueError):
        ZwaveValueID()
