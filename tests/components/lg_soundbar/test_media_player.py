"""Test the lg_soundbar media player."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiotemescal
from aiotemescal import TemescalConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import find_connection_callback, find_update_callback, setup_integration

ENTITY_ID = "media_player.127_0_0_1"

AVAILABLE_FUNCTIONS = [
    aiotemescal.functions.index("Wi-Fi"),
    aiotemescal.functions.index("Bluetooth"),
    aiotemescal.functions.index("Optical/HDMI ARC"),
    aiotemescal.functions.index("HDMI"),
    aiotemescal.functions.index("USB2"),
]


def send_func_view_info(callback: MagicMock, current_function: str) -> None:
    """Report the given function as the current one via the callback."""
    callback(
        {
            "msg": "FUNC_VIEW_INFO",
            "data": {
                "i_curr_func": aiotemescal.functions.index(current_function),
                "ai_func_list": AVAILABLE_FUNCTIONS,
            },
        }
    )


async def test_source_reported_as_is_when_available(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a function offered by the device is reported unchanged."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_client), "Bluetooth")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["source"] == "Bluetooth"


async def test_source_falls_back_to_available_equivalent(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a function missing from the list falls back to an equivalent one.

    Soundbars report states such as E-ARC or HDMI3 that they never offer in
    ai_func_list, which leaves the current source outside of source_list.
    """
    await setup_integration(hass, mock_config_entry)
    callback = find_update_callback(mock_client)

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
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a function without an available equivalent is reported as is."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_client), "Aux")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["source"] == "Aux"


async def test_source_list_only_contains_offered_functions(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the source list is not extended by the fallback."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_client), "E-ARC")
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
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no source is reported before the device answers."""
    await setup_integration(hass, mock_config_entry)

    assert "source" not in hass.states.get(ENTITY_ID).attributes


# An SG10TY reports these alongside indices the library knows about. They sit
# past the end of its table.
UNMAPPED_EQUALISERS = [23, 24, 25, 26]

AVAILABLE_EQUALISERS = [
    aiotemescal.equalisers.index("Standard"),
    aiotemescal.equalisers.index("Cinema"),
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
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that equalisers the library cannot name are still offered."""
    await setup_integration(hass, mock_config_entry)

    send_eq_view_info(find_update_callback(mock_client), 23)
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
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an equaliser the library cannot name can be selected."""
    await setup_integration(hass, mock_config_entry)

    send_eq_view_info(find_update_callback(mock_client), 0)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "Unknown (25)"},
        blocking=True,
    )

    mock_client.set_eq.assert_awaited_once_with(25)


async def test_selecting_a_named_sound_mode(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an equaliser the library can name is still selectable."""
    await setup_integration(hass, mock_config_entry)

    send_eq_view_info(find_update_callback(mock_client), 0)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "Cinema"},
        blocking=True,
    )

    mock_client.set_eq.assert_awaited_once_with(aiotemescal.equalisers.index("Cinema"))


async def test_selecting_a_source_the_device_does_not_offer(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a known function outside of ai_func_list stays selectable."""
    await setup_integration(hass, mock_config_entry)

    send_func_view_info(find_update_callback(mock_client), "Bluetooth")
    await hass.async_block_till_done()

    assert "E-ARC" not in hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "E-ARC"},
        blocking=True,
    )

    mock_client.set_func.assert_awaited_once_with(aiotemescal.functions.index("E-ARC"))


def send_play_info(callback: MagicMock, stream_type: int) -> None:
    """Report the given stream type via the callback."""
    callback({"msg": "PLAY_INFO", "data": {"i_stream_type": stream_type}})


def send_power_status(callback: MagicMock, powered_on: bool) -> None:
    """Report the given power status via the callback."""
    callback({"msg": "SPK_LIST_VIEW_INFO", "data": {"b_powerstatus": powered_on}})


async def test_state_stays_on_without_a_reported_power_status(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a soundbar that never reports a power status stays on.

    Being used as a soundbar is the ordinary case for such a model, so the
    stream type it reports for that must not be read as powered off.
    """
    await setup_integration(hass, mock_config_entry)

    send_play_info(find_update_callback(mock_client), 0)
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
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    powered_on: bool,
    expected_state: MediaPlayerState,
) -> None:
    """Test that a reported power status decides the state of a soundbar."""
    await setup_integration(hass, mock_config_entry)

    callback = find_update_callback(mock_client)
    send_power_status(callback, powered_on)
    send_play_info(callback, 0)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == expected_state


async def test_availability_follows_the_connection(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entity is unavailable while the soundbar is unreachable."""
    mock_client.connected = False
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    mock_client.get_info.assert_not_awaited()

    find_connection_callback(mock_client)(True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.ON
    mock_client.get_info.assert_awaited_once()

    find_connection_callback(mock_client)(False)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_state_is_fetched_when_already_connected(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the state is fetched if the device connected before the entity."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == MediaPlayerState.ON
    for request in (
        mock_client.get_product_info,
        mock_client.get_mac_info,
        mock_client.get_eq,
        mock_client.get_info,
        mock_client.get_func,
        mock_client.get_settings,
        mock_client.get_play,
    ):
        request.assert_awaited_once()


async def test_lost_connection_while_fetching_the_state(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a connection lost during the refresh is left to the client."""
    mock_client.get_eq.side_effect = TemescalConnectionError

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_client.get_info.assert_not_awaited()


async def test_action_while_connection_is_lost(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an action failing to reach the soundbar raises an error."""
    await setup_integration(hass, mock_config_entry)
    mock_client.set_volume.side_effect = TemescalConnectionError("gone")

    with pytest.raises(HomeAssistantError, match="gone") as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            blocking=True,
        )

    assert exc_info.value.translation_key == "communication_error"


@pytest.mark.parametrize(
    ("service", "data", "command", "args"),
    [
        pytest.param(SERVICE_TURN_ON, {}, "set_power", (True,), id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, {}, "set_power", (False,), id="turn_off"),
        pytest.param(
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            "set_mute",
            (True,),
            id="mute",
        ),
        pytest.param(
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            "set_volume",
            (20,),
            id="volume",
        ),
        pytest.param(SERVICE_MEDIA_PLAY, {}, "set_play_ctrl", (True,), id="play"),
        pytest.param(SERVICE_MEDIA_PAUSE, {}, "set_play_ctrl", (False,), id="pause"),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    command: str,
    args: tuple[Any, ...],
) -> None:
    """Test actions are sent to the soundbar."""
    await setup_integration(hass, mock_config_entry)
    callback = find_update_callback(mock_client)
    callback({"msg": "SPK_LIST_VIEW_INFO", "data": {"i_vol_max": 40}})
    callback({"msg": "PLAY_INFO", "data": {"b_support_play_ctrl": True}})
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )

    getattr(mock_client, command).assert_awaited_once_with(*args)


STREAMING = {
    "SPK_LIST_VIEW_INFO": {
        "i_vol": 12,
        "i_vol_min": 0,
        "i_vol_max": 40,
        "b_mute": False,
        "i_curr_func": aiotemescal.functions.index("Wi-Fi"),
        "b_powerstatus": True,
    },
    "FUNC_VIEW_INFO": {"ai_func_list": AVAILABLE_FUNCTIONS},
    "SETTING_VIEW_INFO": {
        "i_rear_min": 0,
        "i_rear_max": 10,
        "i_rear_level": 5,
        "i_woofer_min": -15,
        "i_woofer_max": 6,
        "i_woofer_level": 0,
        "i_curr_eq": aiotemescal.equalisers.index("Cinema"),
        "s_user_name": "Salle TV",
    },
    "EQ_VIEW_INFO": {
        "i_bass": 2,
        "i_treble": 3,
        "ai_eq_list": AVAILABLE_EQUALISERS,
    },
    "PLAY_INFO": {
        "i_stream_type": 1,
        "i_play_ctrl": 0,
        "b_support_play_ctrl": True,
        "s_albumart": "http://1.1.1.1/cover.jpg ",
        "s_artist": "Artist",
        "s_title": "Title",
    },
}


@pytest.mark.parametrize(
    "messages",
    [
        pytest.param(STREAMING, id="playing"),
        pytest.param(
            {**STREAMING, "PLAY_INFO": {**STREAMING["PLAY_INFO"], "i_play_ctrl": 1}},
            id="paused",
        ),
        pytest.param(
            {
                **STREAMING,
                "SPK_LIST_VIEW_INFO": {
                    **STREAMING["SPK_LIST_VIEW_INFO"],
                    "b_mute": True,
                    "b_powerstatus": False,
                },
                "PLAY_INFO": {"i_stream_type": 0, "s_artist": " ", "s_title": ""},
            },
            id="off",
        ),
    ],
)
async def test_state_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    messages: dict[str, dict[str, Any]],
) -> None:
    """Test the state built from the messages of the soundbar."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done(wait_background_tasks=True)

    callback = find_update_callback(mock_client)
    # The entity picture carries a random access token
    with patch("secrets.token_hex", return_value="mock_token"):
        for msg, data in messages.items():
            callback({"msg": msg, "data": data})
    await hass.async_block_till_done(wait_background_tasks=True)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
