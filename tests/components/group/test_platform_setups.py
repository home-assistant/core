"""Tests for platform setups in the group component."""
from homeassistant.components.group.util import no_op


def test_no_op_usage() -> None:
    """Test the no_op function from util.py to ensure it doesn't modify arguments or return any value."""
    hass_argument = "hass_value"
    discovery_info_argument = "discovery_info_value"

    # Duplicate values for comparison after the function call
    duplicate_hass = hass_argument
    duplicate_discovery_info = discovery_info_argument

    # Call the no_op function
    result = no_op(hass_argument, discovery_info_argument)

    # Ensure no_op does not return any value
    assert result is None

    # Ensure no_op didn't modify its arguments
    assert hass_argument == duplicate_hass
    assert discovery_info_argument == duplicate_discovery_info
