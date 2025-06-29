"""Test for helper functions."""

import pytest

from homeassistant.components.lcn.helpers import get_resource
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    ("domain_name", "domain_data", "expected"),
    [
        ("switch", {"output": "RELAY1"}, "RELAY1"),
        ("light", {"output": "OUTPUT1"}, "OUTPUT1"),
        ("binary_sensor", {"source": "BINSENSOR1"}, "BINSENSOR1"),
        ("sensor", {"source": "VAR1"}, "VAR1"),
        ("cover", {"motor": "MOTOR1"}, "MOTOR1"),
        ("climate", {"setpoint": "R1VARSETPOINT"}, "R1VARSETPOINT"),
        ("scene", {"register": 0, "scene": 1}, "01"),
    ],
)
async def test_get_resource(domain_name: str, domain_data: dict, expected: str) -> None:
    """Test get_resource function."""
    assert get_resource(domain_name, domain_data) == expected


async def test_get_resource_invalid_domain() -> None:
    """Test get_resource function with an invalid domain."""
    domain_name = "invalid"
    domain_data = {}
    with pytest.raises(HomeAssistantError):
        get_resource(domain_name, domain_data)
