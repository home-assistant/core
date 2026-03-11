"""Tests for arcam fmj receivers."""

from math import isclose
from unittest.mock import PropertyMock, patch

from arcam.fmj import ConnectionFailed, DecodeMode2CH, DecodeModeMCH, SourceCodes
from arcam.fmj.state import State
import pytest

from homeassistant.components.arcam_fmj.media_player import ArcamFmj
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    SERVICE_SELECT_SOURCE,
    SERVICE_VOLUME_SET,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MOCK_HOST, MOCK_UUID

MOCK_TURN_ON = {
    "service": "switch.turn_on",
    "data": {"entity_id": "switch.test"},
}


async def update(player: ArcamFmj, force_refresh=False):
    """Force a update of player and return current state data."""
    await player.async_update_ha_state(force_refresh=force_refresh)
    return player.hass.states.get(player.entity_id)


async def test_properties(player: ArcamFmj) -> None:
    """Test standard properties."""
    assert player.unique_id == f"{MOCK_UUID}-1"
    assert player.device_info == {
        ATTR_NAME: f"Arcam FMJ ({MOCK_HOST})",
        ATTR_IDENTIFIERS: {
            ("arcam_fmj", MOCK_UUID),
        },
        ATTR_MODEL: "Arcam FMJ AVR",
        ATTR_MANUFACTURER: "Arcam",
    }
    assert not player.should_poll


async def test_powered_off(
    hass: HomeAssistant, player: ArcamFmj, state_1: State
) -> None:
    """Test properties in powered off state."""
    state_1.get_source.return_value = None
    state_1.get_power.return_value = None

    data = await update(player)
    assert "source" not in data.attributes
    assert data.state == "off"


async def test_powered_on(player: ArcamFmj, state_1: State) -> None:
    """Test properties in powered on state."""
    state_1.get_source.return_value = SourceCodes.PVR
    state_1.get_power.return_value = True

    data = await update(player)
    assert data.attributes["source"] == "PVR"
    assert data.state == "on"


async def test_supported_features(player: ArcamFmj) -> None:
    """Test supported features."""
    data = await update(player)
    assert data.attributes["supported_features"] == 200588


async def test_turn_on(player: ArcamFmj, state_1: State) -> None:
    """Test turn on service."""
    state_1.get_power.return_value = None
    await player.async_turn_on()
    state_1.set_power.assert_not_called()

    state_1.get_power.return_value = False
    await player.async_turn_on()
    state_1.set_power.assert_called_with(True)


async def test_turn_off(player: ArcamFmj, state_1: State) -> None:
    """Test command to turn off."""
    await player.async_turn_off()
    state_1.set_power.assert_called_with(False)


@pytest.mark.parametrize("mute", [True, False])
async def test_mute_volume(player: ArcamFmj, state_1: State, mute: bool) -> None:
    """Test mute functionality."""
    await player.async_mute_volume(mute)
    state_1.set_mute.assert_called_with(mute)
    player.async_write_ha_state.assert_called_with()


async def test_name(player: ArcamFmj) -> None:
    """Test name."""
    data = await update(player)
    assert data.attributes["friendly_name"] == "Zone 1"


async def test_update(hass: HomeAssistant, player_setup: str, state_1: State) -> None:
    """Test update."""
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: player_setup},
        blocking=True,
    )
    state_1.update.assert_called_with()


async def test_update_lost(
    hass: HomeAssistant,
    player_setup: str,
    state_1: State,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update, with connection loss is ignored."""
    state_1.update.side_effect = ConnectionFailed()

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: player_setup},
        blocking=True,
    )
    state_1.update.assert_called_with()


@pytest.mark.parametrize(
    ("source", "value"),
    [("PVR", SourceCodes.PVR), ("BD", SourceCodes.BD), ("INVALID", None)],
)
async def test_select_source(
    hass: HomeAssistant,
    player_setup,
    state_1: State,
    source: str,
    value: SourceCodes | None,
) -> None:
    """Test selection of source."""
    await hass.services.async_call(
        "media_player",
        SERVICE_SELECT_SOURCE,
        service_data={ATTR_ENTITY_ID: player_setup, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    if value:
        state_1.set_source.assert_called_with(value)
    else:
        state_1.set_source.assert_not_called()


async def test_source_list(player: ArcamFmj, state_1: State) -> None:
    """Test source list."""
    state_1.get_source_list.return_value = [SourceCodes.BD]
    data = await update(player)
    assert data.attributes["source_list"] == ["BD"]


@pytest.mark.parametrize(
    "mode",
    [
        "STEREO",
        "DOLBY_PL",
    ],
)
async def test_select_sound_mode(player: ArcamFmj, state_1: State, mode: str) -> None:
    """Test selection sound mode."""
    await player.async_select_sound_mode(mode)
    state_1.set_decode_mode.assert_called_with(mode)


async def test_volume_up(player: ArcamFmj, state_1: State) -> None:
    """Test mute functionality."""
    await player.async_volume_up()
    state_1.inc_volume.assert_called_with()
    player.async_write_ha_state.assert_called_with()


async def test_volume_down(player: ArcamFmj, state_1: State) -> None:
    """Test mute functionality."""
    await player.async_volume_down()
    state_1.dec_volume.assert_called_with()
    player.async_write_ha_state.assert_called_with()


@pytest.mark.parametrize(
    ("mode", "mode_enum"),
    [
        ("STEREO", DecodeMode2CH.STEREO),
        ("STEREO_DOWNMIX", DecodeModeMCH.STEREO_DOWNMIX),
        (None, None),
    ],
)
async def test_sound_mode(player: ArcamFmj, state_1: State, mode, mode_enum) -> None:
    """Test selection sound mode."""
    state_1.get_decode_mode.return_value = mode_enum
    data = await update(player)
    assert data.attributes.get(ATTR_SOUND_MODE) == mode


@pytest.mark.parametrize(
    ("modes", "modes_enum"),
    [
        (["STEREO", "DOLBY_PL"], [DecodeMode2CH.STEREO, DecodeMode2CH.DOLBY_PL]),
        (["STEREO_DOWNMIX"], [DecodeModeMCH.STEREO_DOWNMIX]),
        (None, None),
    ],
)
async def test_sound_mode_list(
    player: ArcamFmj, state_1: State, modes, modes_enum
) -> None:
    """Test sound mode list."""
    state_1.get_decode_modes.return_value = modes_enum
    data = await update(player)
    assert data.attributes.get(ATTR_SOUND_MODE_LIST) == modes


async def test_is_volume_muted(player: ArcamFmj, state_1: State) -> None:
    """Test muted."""
    state_1.get_mute.return_value = True
    assert player.is_volume_muted is True
    state_1.get_mute.return_value = False
    assert player.is_volume_muted is False
    state_1.get_mute.return_value = None
    assert player.is_volume_muted is None


async def test_volume_level(player: ArcamFmj, state_1: State) -> None:
    """Test volume."""
    state_1.get_volume.return_value = 0
    assert isclose(player.volume_level, 0.0)
    state_1.get_volume.return_value = 50
    assert isclose(player.volume_level, 50.0 / 99)
    state_1.get_volume.return_value = 99
    assert isclose(player.volume_level, 1.0)
    state_1.get_volume.return_value = None
    assert player.volume_level is None


@pytest.mark.parametrize(("volume", "call"), [(0.0, 0), (0.5, 50), (1.0, 99)])
async def test_set_volume_level(
    hass: HomeAssistant, player_setup: str, state_1: State, volume, call
) -> None:
    """Test setting volume."""

    await hass.services.async_call(
        "media_player",
        SERVICE_VOLUME_SET,
        service_data={ATTR_ENTITY_ID: player_setup, ATTR_MEDIA_VOLUME_LEVEL: volume},
        blocking=True,
    )

    state_1.set_volume.assert_called_with(call)


async def test_set_volume_level_lost(
    hass: HomeAssistant, player_setup: str, state_1: State
) -> None:
    """Test setting volume, with a lost connection."""

    state_1.set_volume.side_effect = ConnectionFailed()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            SERVICE_VOLUME_SET,
            service_data={ATTR_ENTITY_ID: player_setup, ATTR_MEDIA_VOLUME_LEVEL: 0.0},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("source", "media_content_type"),
    [
        (SourceCodes.DAB, MediaType.MUSIC),
        (SourceCodes.FM, MediaType.MUSIC),
        (SourceCodes.PVR, None),
        (None, None),
    ],
)
async def test_media_content_type(
    player: ArcamFmj, state_1: State, source, media_content_type
) -> None:
    """Test content type deduction."""
    state_1.get_source.return_value = source
    assert player.media_content_type == media_content_type


@pytest.mark.parametrize(
    ("source", "dab", "rds", "channel"),
    [
        (SourceCodes.DAB, "dab", "rds", "dab"),
        (SourceCodes.DAB, None, None, None),
        (SourceCodes.FM, "dab", "rds", "rds"),
        (SourceCodes.FM, None, None, None),
        (SourceCodes.PVR, "dab", "rds", None),
    ],
)
async def test_media_channel(
    player: ArcamFmj, state_1: State, source, dab, rds, channel
) -> None:
    """Test media channel."""
    state_1.get_dab_station.return_value = dab
    state_1.get_rds_information.return_value = rds
    state_1.get_source.return_value = source
    assert player.media_channel == channel


@pytest.mark.parametrize(
    ("source", "dls", "artist"),
    [
        (SourceCodes.DAB, "dls", "dls"),
        (SourceCodes.FM, "dls", None),
        (SourceCodes.DAB, None, None),
    ],
)
async def test_media_artist(
    player: ArcamFmj, state_1: State, source, dls, artist
) -> None:
    """Test media artist."""
    state_1.get_dls_pdt.return_value = dls
    state_1.get_source.return_value = source
    assert player.media_artist == artist


@pytest.mark.parametrize(
    ("source", "channel", "title"),
    [
        (SourceCodes.DAB, "channel", "DAB - channel"),
        (SourceCodes.DAB, None, "DAB"),
        (None, None, None),
    ],
)
async def test_media_title(
    player: ArcamFmj, state_1: State, source, channel, title
) -> None:
    """Test media title."""

    state_1.get_source.return_value = source
    with patch.object(
        ArcamFmj, "media_channel", new_callable=PropertyMock
    ) as media_channel:
        media_channel.return_value = channel
        data = await update(player)
        if title is None:
            assert "media_title" not in data.attributes
        else:
            assert data.attributes["media_title"] == title
