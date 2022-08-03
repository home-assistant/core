"""Tests for the Aqara switch device."""
# from unittest.mock import patch


from homeassistant.components.aqara import (
    # remap_value,
    string_dot_to_underline,
    string_underline_to_dot,
)

# from homeassistant.const import (
#     ATTR_ENTITY_ID,
#     SERVICE_TURN_OFF,
#     SERVICE_TURN_ON,
#     STATE_OFF,
#     STATE_ON,
# )
from homeassistant.core import HomeAssistant

# from homeassistant.helpers import entity_registry as er
# from .common import setup_platform
# from homeassistant.const import (
#     ATTR_ENTITY_ID,
#     SERVICE_TURN_OFF,
#     SERVICE_TURN_ON,
#     STATE_UNKNOWN,
# )


async def test_remap_value(hass: HomeAssistant) -> None:
    """Tests remap_value."""
    # print(remap_value(10, 0, 100, 0, 50, False))
    # assert remap_value(10, 0, 100, 0, 50, True) == 20
    assert string_dot_to_underline("lumi.53523534__4.1.85") == "lumi_53523534__4_1_85"
    assert string_underline_to_dot("lumi_53523534__4_1_85") == "lumi.53523534__4.1.85"


# def remap_value(
#     value: float | int,
#     from_min: float | int = 0,
#     from_max: float | int = 255,
#     to_min: float | int = 0,
#     to_max: float | int = 255,
#     reverse: bool = False,
# ) -> float:
#     """Remap a value from its current range, to a new range."""
#     if reverse:
#         value = from_max - value + from_min
#     return ((value - from_min) / (from_max - from_min)) * (to_max - to_min) + to_min


# def string_dot_to_underline(data: str) -> str:
#     """Replace dot to underline. lumi.53523534__4.1.85     ->  lumi_53523534__4_1_85"""  #
#     new_data = data.replace(".", "_")
#     return new_data


# def string_underline_to_dot(data: str) -> str:
#     """Replaceunderline to dot. lumi_53523534__4_1_85    ->  lumi.53523534__4.1.85"""
#     new_data = data.replace("__", "--").replace("_", ".").replace("--", "__")
#     return new_data
