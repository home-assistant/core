"""Test the lg_soundbar media player."""

from unittest.mock import MagicMock

import pytest
import temescal

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID
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


# An SG10TY reports these alongside indices temescal knows about. They sit past
# the end of the library's table, which has been read-only since 2023.
UNMAPPED_EQUALISERS = [23, 24, 25, 26]

AVAILABLE_EQUALISERS = [
    temescal.equalisers.index("Standard"),
    temescal.equalisers.index("Cinema"),
    *UNMAPPED_EQUALISERS,
]


def send_eq_view_info(callback: MagicMock, current_equaliser: int) -> None:
    """Report the given equaliser as the current one via the callback."""
    callback(
        {
            "msg": "EQ_VIEW_INFO",
            "data": {
                "i_curr_eq": current_equaliser,
                "ai_eq_list": AVAILABLE_EQUALISERS,
            },
        }
    )


async def test_sound_modes_beyond_the_library_table_are_offered(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that equalisers the library cannot name are still offered."""
    await setup_integration(hass, mock_config_entry)

    send_eq_view_info(find_update_callback(mock_temescal), 23)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_SOUND_MODE_LIST] == [
        "Cinema",
        "Standard",
        "Unknown (23)",
        "Unknown (24)",
        "Unknown (25)",
        "Unknown (26)",
    ]
    assert state.attributes[ATTR_SOUND_MODE] == "Unknown (23)"


async def test_selecting_a_sound_mode_beyond_the_library_table(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an equaliser the library cannot name can be selected."""
    await setup_integration(hass, mock_config_entry)

    send_eq_view_info(find_update_callback(mock_temescal), 0)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "Unknown (25)"},
        blocking=True,
    )

    mock_temescal.return_value.set_eq.assert_called_once_with(25)


async def test_selecting_a_named_sound_mode(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an equaliser the library can name is still selectable."""
    await setup_integration(hass, mock_config_entry)

    send_eq_view_info(find_update_callback(mock_temescal), 0)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "Cinema"},
        blocking=True,
    )

    mock_temescal.return_value.set_eq.assert_called_once_with(
        temescal.equalisers.index("Cinema")
    )


async def test_selecting_a_source_the_device_does_not_offer(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a known function outside of ai_func_list stays selectable."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_temescal), "Bluetooth")
    await hass.async_block_till_done()

    assert "E-ARC" not in hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "E-ARC"},
        blocking=True,
    )

    mock_temescal.return_value.set_func.assert_called_once_with(
        temescal.functions.index("E-ARC")
    )


def send_play_info(callback: MagicMock, stream_type: int) -> None:
    """Report the given stream type via the callback."""
    callback({"msg": "PLAY_INFO", "data": {"i_stream_type": stream_type}})


def send_power_status(callback: MagicMock, powered_on: bool) -> None:
    """Report the given power status via the callback."""
    callback({"msg": "SPK_LIST_VIEW_INFO", "data": {"b_powerstatus": powered_on}})


async def test_state_stays_on_without_a_reported_power_status(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a soundbar that never reports a power status stays on.

    Being used as a soundbar is the ordinary case for such a model, so the
    stream type it reports for that must not be read as powered off.
    """
    await setup_integration(hass, mock_config_entry)

    send_play_info(find_update_callback(mock_temescal), 0)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.ON


@pytest.mark.parametrize(
    ("powered_on", "expected_state"),
    [
        pytest.param(True, MediaPlayerState.ON, id="on"),
        pytest.param(False, MediaPlayerState.OFF, id="off"),
    ],
)
async def test_state_follows_a_reported_power_status(
    hass: HomeAssistant,
    mock_temescal: MagicMock,
    mock_config_entry: MockConfigEntry,
    powered_on: bool,
    expected_state: MediaPlayerState,
) -> None:
    """Test that a reported power status decides the state of a soundbar."""
    await setup_integration(hass, mock_config_entry)

    callback = find_update_callback(mock_temescal)
    send_power_status(callback, powered_on)
    send_play_info(callback, 0)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == expected_state
