"""Tests for the Aqara switch device."""
# from unittest.mock import patch


from homeassistant.components.aqara import (  # remap_value,
    string_dot_to_underline,
    string_underline_to_dot,
)
from homeassistant.core import HomeAssistant


async def test_remap_value(hass: HomeAssistant) -> None:
    """Tests remap_value."""
    # print(remap_value(10, 0, 100, 0, 50, False))
    # assert remap_value(10, 0, 100, 0, 50, True) == 20
    assert string_dot_to_underline("lumi.53523534__4.1.85") == "lumi_53523534__4_1_85"
    assert string_underline_to_dot("lumi_53523534__4_1_85") == "lumi.53523534__4.1.85"
