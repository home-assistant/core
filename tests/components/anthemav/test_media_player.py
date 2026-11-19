"""Test the Anthem A/V Receivers media player."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityCapabilityAttribute,
    MediaPlayerEntityFeature,
    MediaPlayerEntityStateAttribute,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_MODEL,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_update_states_zone1(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_anthemav: AsyncMock,
    update_callback: Callable[[str], None],
) -> None:
    """Test zone states are updated."""

    mock_zone = mock_anthemav.protocol.zones[1]

    mock_zone.power = True
    mock_zone.mute = True
    mock_zone.volume_as_percentage = 42
    mock_zone.input_name = "TEST INPUT"
    mock_zone.input_format = "2.0 PCM"
    mock_anthemav.protocol.input_list = ["TEST INPUT", "INPUT 2"]

    update_callback("command")
    await hass.async_block_till_done()

    states = hass.states.get("media_player.anthem_av")
    assert states
    assert states.state == STATE_ON
    assert states.attributes[MediaPlayerEntityStateAttribute.MEDIA_VOLUME_LEVEL] == 42
    assert states.attributes[MediaPlayerEntityStateAttribute.MEDIA_VOLUME_MUTED] is True
    assert (
        states.attributes[MediaPlayerEntityStateAttribute.INPUT_SOURCE] == "TEST INPUT"
    )
    assert (
        states.attributes[MediaPlayerEntityStateAttribute.MEDIA_TITLE] == "TEST INPUT"
    )
    assert states.attributes[MediaPlayerEntityStateAttribute.APP_NAME] == "2.0 PCM"
    assert states.attributes[
        MediaPlayerEntityCapabilityAttribute.INPUT_SOURCE_LIST
    ] == ["TEST INPUT", "INPUT 2"]


def _reader(*chunks: bytes) -> MagicMock:
    """Return a stream reader that yields chunks, then end of stream."""
    reader = MagicMock()
    reader.read = AsyncMock(side_effect=[*chunks, b""])
    return reader


async def _setup_x10(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_anthemav: AsyncMock
) -> None:
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_MODEL: "MRX 310 "}
    )
    mock_anthemav.protocol.input_list = ["GoogleTV", "SqueezeB"]
    mock_anthemav.protocol._input_numbers = {"GoogleTV": 1, "SqueezeB": 6}
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_connection_create")
async def test_select_source_x10_uses_new_connection(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test MRX x10 input changes are sent over a new connection."""
    await _setup_x10(hass, mock_config_entry, mock_anthemav)
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()

    with (
        patch(
            "asyncio.open_connection", return_value=(_reader(b";"), writer)
        ) as open_connection,
        patch(
            "homeassistant.components.anthemav.single_command.SINGLE_COMMAND_LINGER_SECONDS",
            0,
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_INPUT_SOURCE: "SqueezeB"},
            blocking=True,
        )

    open_connection.assert_called_once_with("1.1.1.1", 14999)
    writer.write.assert_called_once_with(b"Z1INP6;")
    writer.close.assert_called_once()
    mock_anthemav.protocol.zones[1].query.assert_called_with("INP")


@pytest.mark.usefixtures("mock_connection_create")
async def test_select_source_x10_cannot_connect(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error is raised when the new connection fails."""
    await _setup_x10(hass, mock_config_entry, mock_anthemav)

    with (
        patch("asyncio.open_connection", side_effect=OSError("refused")),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_INPUT_SOURCE: "SqueezeB"},
            blocking=True,
        )
    assert err.value.translation_key == "cannot_connect"


@pytest.mark.parametrize("failing_step", ["write", "drain"])
@pytest.mark.usefixtures("mock_connection_create")
async def test_select_source_x10_send_failed(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
    failing_step: str,
) -> None:
    """Test an error is raised and the connection closed when sending fails."""
    await _setup_x10(hass, mock_config_entry, mock_anthemav)
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    getattr(writer, failing_step).side_effect = OSError("reset")
    mock_zone = mock_anthemav.protocol.zones[1]
    mock_zone.query.reset_mock()

    with (
        patch("asyncio.open_connection", return_value=(MagicMock(), writer)),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_INPUT_SOURCE: "SqueezeB"},
            blocking=True,
        )
    assert err.value.translation_key == "send_failed"
    writer.close.assert_called_once()
    mock_zone.query.assert_not_called()


@pytest.mark.usefixtures("mock_connection_create")
async def test_select_source_x10_unknown_source(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a source the receiver doesn't have."""
    await _setup_x10(hass, mock_config_entry, mock_anthemav)

    with (
        patch("asyncio.open_connection") as open_connection,
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_INPUT_SOURCE: "Nope"},
            blocking=True,
        )
    open_connection.assert_not_called()


async def test_select_source_other_models(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_anthemav: AsyncMock,
) -> None:
    """Test other models change input over the existing connection."""
    with patch("asyncio.open_connection") as open_connection:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_INPUT_SOURCE: "INPUT 2"},
            blocking=True,
        )
    open_connection.assert_not_called()
    assert mock_anthemav.protocol.zones[1].input_name == "INPUT 2"


ALM_NUMBERS = {"None": 0, "AnthemLogic Cinema": 1, "PLII Music": 4}
SINGLE_COMMAND_LINGER = (
    "homeassistant.components.anthemav.single_command.SINGLE_COMMAND_LINGER_SECONDS"
)


async def test_sound_mode_state(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_connection_create: AsyncMock,
) -> None:
    """Test zone 1 reports the listening mode and zone 2 doesn't."""
    mock_anthemav.protocol.audio_listening_mode_list = list(ALM_NUMBERS)
    mock_anthemav.protocol.audio_listening_mode_text = "PLII Music"
    mock_anthemav.protocol.zones[1].power = True
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.anthem_av")
    assert state.attributes[ATTR_SOUND_MODE] == "PLII Music"
    assert state.attributes[ATTR_SOUND_MODE_LIST] == list(ALM_NUMBERS)
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    zone_2 = hass.states.get("media_player.zone_2")
    assert not (
        zone_2.attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )


async def test_select_sound_mode_other_models(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_connection_create: AsyncMock,
) -> None:
    """Test other models change the listening mode over the existing connection."""
    mock_anthemav.protocol._alm_number = ALM_NUMBERS
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("asyncio.open_connection") as open_connection:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_SOUND_MODE: "PLII Music"},
            blocking=True,
        )
    open_connection.assert_not_called()
    assert mock_anthemav.protocol.audio_listening_mode == 4


def _receiver(answers: dict[bytes, bytes]) -> tuple[MagicMock, MagicMock]:
    """Return a stream reader and writer for a receiver giving these answers.

    A command without an answer gets no reply at all.
    """
    pending: asyncio.Queue[bytes] = asyncio.Queue()
    writer = MagicMock()
    writer.write.side_effect = lambda data: pending.put_nowait(answers.get(data, b""))
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()

    async def read(_: int) -> bytes:
        while not (data := await pending.get()):
            pass
        return data

    reader = MagicMock()
    reader.read = read
    return reader, writer


@pytest.mark.parametrize(
    ("answers", "sent"),
    [
        pytest.param(
            {b"Z1ALM04;": b"Z1AIF0;Z1ALM04;Z1AIF3;"},
            [b"Z1ALM04;"],
            id="applied",
        ),
        pytest.param(
            {b"Z1ALM04;": b";", b"Z1ALM?;": b"Z1ALM04;"},
            [b"Z1ALM04;", b"Z1ALM?;"],
            id="already_active",
        ),
    ],
)
@pytest.mark.usefixtures("mock_connection_create")
async def test_select_sound_mode_x10(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
    answers: dict[bytes, bytes],
    sent: list[bytes],
) -> None:
    """Test MRX x10 listening mode changes are sent and confirmed."""
    mock_anthemav.protocol._alm_number = ALM_NUMBERS
    await _setup_x10(hass, mock_config_entry, mock_anthemav)
    reader, writer = _receiver(answers)

    with (
        patch("asyncio.open_connection", return_value=(reader, writer)),
        patch(SINGLE_COMMAND_LINGER, 0.05),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_SOUND_MODE: "PLII Music"},
            blocking=True,
        )

    assert writer.write.call_args_list == [call(data) for data in sent]
    writer.close.assert_called_once()
    mock_anthemav.protocol.query.assert_called_with("Z1ALM")


@pytest.mark.usefixtures("mock_connection_create")
async def test_select_sound_mode_unknown(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a listening mode the receiver doesn't have."""
    mock_anthemav.protocol._alm_number = ALM_NUMBERS
    await _setup_x10(hass, mock_config_entry, mock_anthemav)

    with (
        patch("asyncio.open_connection") as open_connection,
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_SOUND_MODE: "Nope"},
            blocking=True,
        )
    open_connection.assert_not_called()


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param({b"Z1ALM?;": b"Z1ALM03;"}, id="not_available_for_source"),
        pytest.param(
            {b"Z1ALM04;": b"!RZ1ALM04;", b"Z1ALM?;": b"Z1ALM03;"},
            id="out_of_range",
        ),
    ],
)
@pytest.mark.usefixtures("mock_connection_create")
async def test_select_sound_mode_x10_not_applied(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
    answers: dict[bytes, bytes],
) -> None:
    """Test an error is raised when the receiver doesn't switch modes."""
    mock_anthemav.protocol._alm_number = ALM_NUMBERS
    await _setup_x10(hass, mock_config_entry, mock_anthemav)
    reader, writer = _receiver(answers)

    with (
        patch("asyncio.open_connection", return_value=(reader, writer)),
        patch(SINGLE_COMMAND_LINGER, 0.05),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_ENTITY_ID: "media_player.anthem_av", ATTR_SOUND_MODE: "PLII Music"},
            blocking=True,
        )
    assert err.value.translation_key == "sound_mode_not_applied"
    # The main connection is still asked for the actual mode.
    mock_anthemav.protocol.query.assert_called_with("Z1ALM")


async def test_no_sound_mode_for_x40(
    hass: HomeAssistant,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_connection_create: AsyncMock,
) -> None:
    """Test x40 receivers get no sound mode, as the library misnames their modes."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_MODEL: "MRX 740"}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.anthem_av")
    assert not (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
