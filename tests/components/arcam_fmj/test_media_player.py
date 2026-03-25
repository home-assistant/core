"""Tests for arcam fmj receivers."""

from math import isclose
from unittest.mock import Mock, PropertyMock, patch

from arcam.fmj import ConnectionFailed, DecodeMode2CH, DecodeModeMCH, SourceCodes
from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.arcam_fmj.media_player import ArcamFmj
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, State as CoreState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_ENTITY_ID

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platform_fixture():
    """Only test single platform."""
    with patch("homeassistant.components.arcam_fmj.PLATFORMS", [Platform.MEDIA_PLAYER]):
        yield


@pytest.mark.usefixtures("player_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup creates expected entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def update(hass: HomeAssistant, client: Mock, entity_id: str) -> CoreState:
    """Force a update of player and return current state data."""
    client.notify_data_updated()
    await hass.async_block_till_done()
    data = hass.states.get(entity_id)
    assert data
    return data


@pytest.mark.usefixtures("player_setup")
async def test_powered_off(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test properties in powered off state."""
    state_1.get_source.return_value = None
    state_1.get_power.return_value = None

    data = await update(hass, client, MOCK_ENTITY_ID)
    assert "source" not in data.attributes
    assert data.state == "off"


@pytest.mark.usefixtures("player_setup")
async def test_powered_on(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test properties in powered on state."""
    state_1.get_source.return_value = SourceCodes.PVR
    state_1.get_power.return_value = True

    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes["source"] == "PVR"
    assert data.state == "on"


@pytest.mark.usefixtures("player_setup")
async def test_turn_on(hass: HomeAssistant, state_1: State) -> None:
    """Test turn on service."""
    state_1.get_power.return_value = None
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.set_power.assert_not_called()

    state_1.get_power.return_value = False
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.set_power.assert_called_with(True)


@pytest.mark.usefixtures("player_setup")
async def test_turn_off(hass: HomeAssistant, state_1: State) -> None:
    """Test command to turn off."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.set_power.assert_called_with(False)


@pytest.mark.parametrize("mute", [True, False])
@pytest.mark.usefixtures("player_setup")
async def test_mute_volume(hass: HomeAssistant, state_1: State, mute: bool) -> None:
    """Test mute functionality."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: mute},
        blocking=True,
    )
    state_1.set_mute.assert_called_with(mute)


@pytest.mark.usefixtures("player_setup")
async def test_update(hass: HomeAssistant, state_1: State) -> None:
    """Test update."""
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.update.assert_called_with()


@pytest.mark.usefixtures("player_setup")
async def test_update_lost(
    hass: HomeAssistant,
    state_1: State,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update, with connection loss is ignored."""
    state_1.update.side_effect = ConnectionFailed()

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.update.assert_called_with()


@pytest.mark.parametrize(
    ("source", "value"),
    [("PVR", SourceCodes.PVR), ("BD", SourceCodes.BD), ("INVALID", None)],
)
@pytest.mark.usefixtures("player_setup")
async def test_select_source(
    hass: HomeAssistant,
    state_1: State,
    source: str,
    value: SourceCodes | None,
) -> None:
    """Test selection of source."""
    await hass.services.async_call(
        "media_player",
        SERVICE_SELECT_SOURCE,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    if value:
        state_1.set_source.assert_called_with(value)
    else:
        state_1.set_source.assert_not_called()


@pytest.mark.usefixtures("player_setup")
async def test_source_list(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test source list."""
    state_1.get_source_list.return_value = [SourceCodes.BD]
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes["source_list"] == ["BD"]


@pytest.mark.parametrize(
    "mode",
    [
        "STEREO",
        "DOLBY_PL",
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_select_sound_mode(
    hass: HomeAssistant, state_1: State, mode: str
) -> None:
    """Test selection sound mode."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_SOUND_MODE: mode},
        blocking=True,
    )
    state_1.set_decode_mode.assert_called_with(mode)


@pytest.mark.usefixtures("player_setup")
async def test_volume_up(hass: HomeAssistant, state_1: State) -> None:
    """Test mute functionality."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.inc_volume.assert_called_with()


@pytest.mark.usefixtures("player_setup")
async def test_volume_down(hass: HomeAssistant, state_1: State) -> None:
    """Test mute functionality."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID},
        blocking=True,
    )
    state_1.dec_volume.assert_called_with()


@pytest.mark.parametrize(
    ("mode", "mode_enum"),
    [
        ("STEREO", DecodeMode2CH.STEREO),
        ("STEREO_DOWNMIX", DecodeModeMCH.STEREO_DOWNMIX),
        (None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_sound_mode(
    hass: HomeAssistant, client: Mock, state_1: State, mode, mode_enum
) -> None:
    """Test selection sound mode."""
    state_1.get_decode_mode.return_value = mode_enum
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_SOUND_MODE) == mode


@pytest.mark.parametrize(
    ("modes", "modes_enum"),
    [
        (["STEREO", "DOLBY_PL"], [DecodeMode2CH.STEREO, DecodeMode2CH.DOLBY_PL]),
        (["STEREO_DOWNMIX"], [DecodeModeMCH.STEREO_DOWNMIX]),
        (None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_sound_mode_list(
    hass: HomeAssistant, client: Mock, state_1: State, modes, modes_enum
) -> None:
    """Test sound mode list."""
    state_1.get_decode_modes.return_value = modes_enum
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_SOUND_MODE_LIST) == modes


@pytest.mark.usefixtures("player_setup")
async def test_is_volume_muted(
    hass: HomeAssistant, client: Mock, state_1: State
) -> None:
    """Test muted."""
    state_1.get_mute.return_value = True
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True

    state_1.get_mute.return_value = False
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is False

    state_1.get_mute.return_value = None
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is None


@pytest.mark.usefixtures("player_setup")
async def test_volume_level(hass: HomeAssistant, client: Mock, state_1: State) -> None:
    """Test volume."""
    state_1.get_volume.return_value = 0
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert isclose(data.attributes[ATTR_MEDIA_VOLUME_LEVEL], 0.0)

    state_1.get_volume.return_value = 50
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert isclose(data.attributes[ATTR_MEDIA_VOLUME_LEVEL], 50.0 / 99)

    state_1.get_volume.return_value = 99
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert isclose(data.attributes[ATTR_MEDIA_VOLUME_LEVEL], 1.0)

    state_1.get_volume.return_value = None
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert ATTR_MEDIA_VOLUME_LEVEL not in data.attributes


@pytest.mark.parametrize(("volume", "call"), [(0.0, 0), (0.5, 50), (1.0, 99)])
@pytest.mark.usefixtures("player_setup")
async def test_set_volume_level(
    hass: HomeAssistant, state_1: State, volume, call
) -> None:
    """Test setting volume."""

    await hass.services.async_call(
        "media_player",
        SERVICE_VOLUME_SET,
        service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: volume},
        blocking=True,
    )

    state_1.set_volume.assert_called_with(call)


@pytest.mark.usefixtures("player_setup")
async def test_set_volume_level_lost(hass: HomeAssistant, state_1: State) -> None:
    """Test setting volume, with a lost connection."""

    state_1.set_volume.side_effect = ConnectionFailed()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            SERVICE_VOLUME_SET,
            service_data={ATTR_ENTITY_ID: MOCK_ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.0},
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
@pytest.mark.usefixtures("player_setup")
async def test_media_content_type(
    hass: HomeAssistant, client: Mock, state_1: State, source, media_content_type
) -> None:
    """Test content type deduction."""
    state_1.get_source.return_value = source
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == media_content_type


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
@pytest.mark.usefixtures("player_setup")
async def test_media_channel(
    hass: HomeAssistant, client: Mock, state_1: State, source, dab, rds, channel
) -> None:
    """Test media channel."""
    state_1.get_dab_station.return_value = dab
    state_1.get_rds_information.return_value = rds
    state_1.get_source.return_value = source
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_CHANNEL) == channel


@pytest.mark.parametrize(
    ("source", "dls", "artist"),
    [
        (SourceCodes.DAB, "dls", "dls"),
        (SourceCodes.FM, "dls", None),
        (SourceCodes.DAB, None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_media_artist(
    hass: HomeAssistant, client: Mock, state_1: State, source, dls, artist
) -> None:
    """Test media artist."""
    state_1.get_dls_pdt.return_value = dls
    state_1.get_source.return_value = source
    data = await update(hass, client, MOCK_ENTITY_ID)
    assert data.attributes.get(ATTR_MEDIA_ARTIST) == artist


@pytest.mark.parametrize(
    ("source", "channel", "title"),
    [
        (SourceCodes.DAB, "channel", "DAB - channel"),
        (SourceCodes.DAB, None, "DAB"),
        (None, None, None),
    ],
)
@pytest.mark.usefixtures("player_setup")
async def test_media_title(
    hass: HomeAssistant, client: Mock, state_1: State, source, channel, title
) -> None:
    """Test media title."""

    state_1.get_source.return_value = source
    with patch.object(
        ArcamFmj, "media_channel", new_callable=PropertyMock
    ) as media_channel:
        media_channel.return_value = channel
        data = await update(hass, client, MOCK_ENTITY_ID)
        if title is None:
            assert "media_title" not in data.attributes
        else:
            assert data.attributes["media_title"] == title
