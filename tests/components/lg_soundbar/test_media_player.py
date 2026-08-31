"""Test the lg_soundbar media player."""

from unittest.mock import MagicMock

import temescal

from homeassistant.components.media_player import ATTR_INPUT_SOURCE_LIST
from homeassistant.core import HomeAssistant

from . import find_update_callback, setup_integration

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.127_0_0_1"

AVAILABLE_FUNCTIONS = [
    temescal.functions.index("Wi-Fi"),
    temescal.functions.index("Bluetooth"),
    temescal.functions.index("Optical/HDMI ARC"),
    temescal.functions.index("HDMI"),
    temescal.functions.index("USB2"),
]


def send_func_view_info(callback: MagicMock, current_function: str) -> None:
    """Report the given function as the current one via the callback."""
    callback(
        {
            "msg": "FUNC_VIEW_INFO",
            "data": {
                "i_curr_func": temescal.functions.index(current_function),
                "ai_func_list": AVAILABLE_FUNCTIONS,
            },
        }
    )


async def test_source_reported_as_is_when_available(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a function offered by the device is reported unchanged."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_temescal), "Bluetooth")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["source"] == "Bluetooth"


async def test_source_falls_back_to_available_equivalent(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a function missing from the list falls back to an equivalent one.

    Soundbars report states such as E-ARC or HDMI3 that they never offer in
    ai_func_list, which leaves the current source outside of source_list.
    """
    await setup_integration(hass, mock_config_entry)
    callback = find_update_callback(mock_temescal)

    send_func_view_info(callback, "E-ARC")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["source"] == "Optical/HDMI ARC"

    send_func_view_info(callback, "ARC")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["source"] == "Optical/HDMI ARC"

    send_func_view_info(callback, "HDMI3")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["source"] == "HDMI"

    send_func_view_info(callback, "USB")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["source"] == "USB2"


async def test_source_kept_when_no_equivalent_is_available(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a function without an available equivalent is reported as is."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_temescal), "Aux")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["source"] == "Aux"


async def test_source_list_only_contains_offered_functions(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the source list is not extended by the fallback."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_temescal), "E-ARC")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST] == [
        "Bluetooth",
        "HDMI",
        "Optical/HDMI ARC",
        "USB2",
        "Wi-Fi",
    ]


async def test_source_unknown_before_any_response(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no source is reported before the device answers."""
    await setup_integration(hass, mock_config_entry)

    assert "source" not in hass.states.get(ENTITY_ID).attributes
