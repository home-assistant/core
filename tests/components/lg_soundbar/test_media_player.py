"""Tests for the lg_soundbar Media Player platform."""
from __future__ import annotations

import socket
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components.lg_soundbar.const import DOMAIN
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant

from . import (
    MOCK_CONFIG,
    MOCK_ENTITY_ID,
    MOCK_MP_ENTITY_ID,
    TEMESCAL_RESPONSES,
    setup_mock_temescal,
)

from tests.common import MockConfigEntry


async def _setup_lg_soundbar(
    hass: HomeAssistant, responses: dict[str, Any] | None = None
) -> MagicMock:
    with patch(
        "homeassistant.components.lg_soundbar.config_flow.QUEUE_TIMEOUT",
        new=0.1,
    ), patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal"
    ) as mock_temescal_config, patch(
        "homeassistant.components.lg_soundbar.media_player.temescal",
    ) as mock_temescal_mp:
        dicts = TEMESCAL_RESPONSES if responses is None else responses
        setup_mock_temescal(
            hass,
            mock_temescal_config,
            msg_dicts=dicts,
        )
        setup_mock_temescal(
            hass,
            mock_temescal_mp,
            msg_dicts=dicts,
        )
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, entry_id=MOCK_ENTITY_ID
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_temescal_mp


async def _call_mp_service(
    hass: HomeAssistant, name: str, data: dict[str, Any]
) -> None:
    return await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, name, service_data=data, blocking=True
    )


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection error."""
    with patch(
        "homeassistant.components.lg_soundbar.media_player.temescal",
    ) as mock_temescal:
        mock_temescal.temescal.side_effect = socket.timeout
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(MOCK_MP_ENTITY_ID) is None


async def test_mute_volume(hass: HomeAssistant) -> None:
    """Test mute functionality."""
    mock_temescal = await _setup_lg_soundbar(hass)
    mock_temescal_instance = mock_temescal.temescal.return_value

    await _call_mp_service(
        hass,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
    )
    await _call_mp_service(
        hass,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
    )
    mock_temescal_instance.set_mute.assert_called_with(False)

    await _call_mp_service(
        hass,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
    )
    mock_temescal_instance.set_mute.assert_called_with(True)


async def test_volume_level(hass: HomeAssistant) -> None:
    """Test set volume level functionality."""
    mock_temescal = await _setup_lg_soundbar(hass)
    mock_temescal_instance = mock_temescal.temescal.return_value

    await _call_mp_service(
        hass,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.0},
    )
    mock_temescal_instance.set_volume.assert_called_with(0)

    await _call_mp_service(hass, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID})
    # mock response i_vol is 10, so 10 + (0.1 * i_vol_max(40)) = 14
    mock_temescal_instance.set_volume.assert_called_with(14)

    await _call_mp_service(
        hass,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
    )
    # 0.5 * i_vol_max(40) = 20
    mock_temescal_instance.set_volume.assert_called_with(20)

    await _call_mp_service(
        hass, SERVICE_VOLUME_DOWN, {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID}
    )
    # i_vol(10) - (0.1 * i_vol_max(40)) = 6
    mock_temescal_instance.set_volume.assert_called_with(6)


async def test_volume_level_max_is_zero(hass: HomeAssistant) -> None:
    """Test set volume level functionality when max volume is 0."""
    responses = TEMESCAL_RESPONSES.copy()
    responses["SPK_LIST_VIEW_INFO"]["i_vol_max"] = 0

    mock_temescal = await _setup_lg_soundbar(hass, responses)
    mock_temescal_instance = mock_temescal.temescal.return_value

    await _call_mp_service(
        hass,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.0},
    )
    mock_temescal_instance.set_volume.assert_called_with(0)

    await _call_mp_service(hass, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID})
    mock_temescal_instance.set_volume.assert_called_with(0)


async def test_select_source(hass: HomeAssistant) -> None:
    """Test select source functionality."""
    mock_temescal = await _setup_lg_soundbar(hass)
    mock_temescal_instance = mock_temescal.temescal.return_value

    assert (
        hass.states.get(MOCK_MP_ENTITY_ID).attributes[ATTR_INPUT_SOURCE]
        == "Optical/HDMI ARC"
    )
    assert await _call_mp_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_INPUT_SOURCE: "Wi-Fi"},
    )
    mock_temescal_instance.set_func.assert_called_with(0)

    assert await _call_mp_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI"},
    )
    mock_temescal_instance.set_func.assert_called_with(6)


async def test_select_source_invalid_source(hass: HomeAssistant) -> None:
    """Test select source functionality when selecting an invalid source."""
    mock_temescal = await _setup_lg_soundbar(hass)
    mock_temescal_instance = mock_temescal.temescal.return_value

    assert await _call_mp_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_INPUT_SOURCE: "non-existent"},
    )
    mock_temescal_instance.set_func.assert_not_called()


async def test_source_list_unlisted_source(hass: HomeAssistant) -> None:
    """Test display of source when soundbar returns an item not in the available source list."""
    responses = TEMESCAL_RESPONSES.copy()
    responses["FUNC_VIEW_INFO"]["i_curr_func"] = 20
    responses["SPK_LIST_VIEW_INFO"]["i_curr_func"] = 20

    assert await _setup_lg_soundbar(hass, responses)
    assert hass.states.get(MOCK_MP_ENTITY_ID).attributes[ATTR_INPUT_SOURCE] == "E-ARC"


async def test_invalid_source_selected(hass: HomeAssistant) -> None:
    """Test source functionality when an invalid source is reported by the sound bar."""
    responses = TEMESCAL_RESPONSES.copy()
    responses["FUNC_VIEW_INFO"]["i_curr_func"] = -1
    responses["SPK_LIST_VIEW_INFO"]["i_curr_func"] = -1

    assert await _setup_lg_soundbar(hass, responses)
    assert ATTR_INPUT_SOURCE not in hass.states.get(MOCK_MP_ENTITY_ID).attributes


async def test_select_sound_mode(hass: HomeAssistant) -> None:
    """Test select sound mode functionality."""
    mock_temescal = await _setup_lg_soundbar(hass)
    mock_temescal_instance = mock_temescal.temescal.return_value

    assert (
        hass.states.get(MOCK_MP_ENTITY_ID).attributes[ATTR_SOUND_MODE] == "AI Sound Pro"
    )
    assert await _call_mp_service(
        hass,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_SOUND_MODE: "Standard"},
    )
    mock_temescal_instance.set_eq.assert_called_with(0)

    assert await _call_mp_service(
        hass,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_SOUND_MODE: "Music"},
    )
    mock_temescal_instance.set_eq.assert_called_with(6)


async def test_select_sound_mode_invalid_mode(hass: HomeAssistant) -> None:
    """Test select sound mode functionality when selecting an invalid mode."""
    mock_temescal = await _setup_lg_soundbar(hass)
    mock_temescal_instance = mock_temescal.temescal.return_value

    assert await _call_mp_service(
        hass,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: MOCK_MP_ENTITY_ID, ATTR_SOUND_MODE: "non-existent"},
    )
    mock_temescal_instance.set_eq.assert_not_called()


async def test_sound_mode_list_unlisted_mode(hass: HomeAssistant) -> None:
    """Test display of sound mode when soundbar returns an item not in the available sound mode list."""
    responses = TEMESCAL_RESPONSES.copy()
    responses["EQ_VIEW_INFO"]["i_curr_eq"] = 1
    responses["SETTING_VIEW_INFO"]["i_curr_eq"] = 1

    assert await _setup_lg_soundbar(hass, responses)
    assert hass.states.get(MOCK_MP_ENTITY_ID).attributes[ATTR_SOUND_MODE] == "Bass"


async def test_invalid_sound_mode_selected(hass: HomeAssistant) -> None:
    """Test sound mode functionality when an invalid sound mode is reported by the sound bar."""
    responses = TEMESCAL_RESPONSES.copy()
    responses["EQ_VIEW_INFO"]["i_curr_eq"] = -1
    responses["SETTING_VIEW_INFO"]["i_curr_eq"] = -1

    assert await _setup_lg_soundbar(hass, responses)
    assert ATTR_SOUND_MODE not in hass.states.get(MOCK_MP_ENTITY_ID).attributes
