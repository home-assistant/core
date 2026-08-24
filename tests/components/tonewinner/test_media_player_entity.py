"""Test the Tonewinner media player entity."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.media_player import (
    ATTR_SOUND_MODE,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.tonewinner.const import DOMAIN
from homeassistant.components.tonewinner.media_player import (
    INPUT_SOURCES,
    SOUND_MODES,
    TonewinnerMediaPlayer,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.at_500"


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Set up the integration against a mocked receiver."""
    with patch(
        "homeassistant.components.tonewinner.TonewinnerReceiver",
        return_value=mock_receiver,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


def _state_callback(mock_receiver: MagicMock) -> Callable[[object], None]:
    """Return the callback the entity registered for receiver state updates."""
    return mock_receiver.subscribe.call_args.args[0]


async def _call_media_player_service(
    hass: HomeAssistant, service: str, **service_data: object
) -> None:
    """Call a media player service on the test entity."""
    await hass.services.async_call(
        "media_player",
        service,
        {"entity_id": ENTITY_ID, **service_data},
        blocking=True,
    )


async def test_media_player_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test media player entity setup."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF
    assert state.attributes["friendly_name"] == "AT-500"

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == mock_config_entry.entry_id


async def test_media_player_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test media player device info comes from stored data without querying."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Tonewinner"
    assert device.model == "AT-500"
    mock_receiver.query_info.assert_not_called()


async def test_media_player_supported_features(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test media player supported features."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["supported_features"] == (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )


async def test_media_player_source_and_sound_mode_lists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test the source list and sound mode list are derived from the library."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["source_list"] == list(INPUT_SOURCES)
    assert state.attributes["sound_mode_list"] == list(SOUND_MODES)


@pytest.mark.parametrize(
    ("volume", "expected"),
    [
        (0.5, 40.0),
        (1.0, 80.0),
        (0.0, 0.0),
        (0.33, 26.5),
    ],
    ids=["half", "max", "zero", "off_grid_snapped"],
)
async def test_media_player_set_volume_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    volume: float,
    expected: float,
) -> None:
    """Test setting volume level maps onto the receiver's half-step grid."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    await _call_media_player_service(hass, "volume_set", volume_level=volume)

    mock_receiver.set_volume.assert_called_once_with(expected)


@pytest.mark.parametrize(
    ("service", "method"),
    [
        ("volume_up", "volume_up"),
        ("volume_down", "volume_down"),
    ],
    ids=["up", "down"],
)
async def test_media_player_volume_step(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    service: str,
    method: str,
) -> None:
    """Test volume stepping delegates to the receiver."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    await _call_media_player_service(hass, service)

    getattr(mock_receiver, method).assert_called_once()


@pytest.mark.parametrize(
    ("mute", "method"),
    [(True, "mute_on"), (False, "mute_off")],
    ids=["on", "off"],
)
async def test_media_player_mute_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    mute: bool,
    method: str,
) -> None:
    """Test muting and unmuting the media player."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    await _call_media_player_service(hass, "volume_mute", is_volume_muted=mute)

    getattr(mock_receiver, method).assert_called_once()


async def test_media_player_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test turning on the media player."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    await _call_media_player_service(hass, "turn_on")

    mock_receiver.power_on.assert_called_once()


async def test_media_player_turn_off_clears_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test turning off the media player clears source state."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    mock_receiver.state.power = True
    mock_receiver.state.source_name = "HDMI 1"
    _state_callback(mock_receiver)(mock_receiver.state)
    await hass.async_block_till_done()

    await _call_media_player_service(hass, "turn_off")

    mock_receiver.power_off.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF
    assert state.attributes.get("source") is None


async def test_media_player_select_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting input source."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    await _call_media_player_service(hass, "select_source", source="HDMI 1")

    mock_receiver.select_source.assert_called_once_with("HD1")


async def test_media_player_select_sound_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting sound mode."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    await _call_media_player_service(hass, "select_sound_mode", sound_mode="Stereo")

    mock_receiver.select_sound_mode.assert_called_once_with("STEREO")


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        ("select_source", {"source": "Nope"}),
        ("select_source", {"source": "HD1"}),
        ("select_sound_mode", {"sound_mode": "Nope"}),
    ],
    ids=["unknown_source", "raw_source_code", "unknown_sound_mode"],
)
async def test_media_player_invalid_selections(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    service: str,
    payload: dict[str, str],
) -> None:
    """Test invalid source and sound mode selections raise an error."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    with pytest.raises(HomeAssistantError):
        await _call_media_player_service(hass, service, **payload)

    mock_receiver.select_source.assert_not_called()
    mock_receiver.select_sound_mode.assert_not_called()


@pytest.mark.parametrize(
    ("state_updates", "attribute", "expected"),
    [
        (
            {"power": True, "volume": 40.0, "source_name": "HDMI 1"},
            "volume_level",
            0.5,
        ),
        (
            {"power": True, "mute": True, "source_name": "HDMI 1"},
            "is_volume_muted",
            True,
        ),
        ({"power": True, "source_name": "HDMI 1"}, "source", "HDMI 1"),
        (
            {"power": True, "sound_mode_label": "Direct", "source_name": "HDMI 1"},
            ATTR_SOUND_MODE,
            "Direct",
        ),
    ],
    ids=["volume", "mute", "source", "sound_mode"],
)
async def test_media_player_state_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    state_updates: dict[str, object],
    attribute: str,
    expected: object,
) -> None:
    """Test receiver state updates are reflected on the entity."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    for key, value in state_updates.items():
        setattr(mock_receiver.state, key, value)
    _state_callback(mock_receiver)(mock_receiver.state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[attribute] == expected
    mock_receiver.query_source.assert_not_called()


async def test_media_player_power_off_from_callback_clears_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test the source clears on power-off and resumes from cache on power-on."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    mock_receiver.state.power = True
    mock_receiver.state.source_name = "HDMI 1"
    _state_callback(mock_receiver)(mock_receiver.state)
    await hass.async_block_till_done()

    mock_receiver.state.power = False
    _state_callback(mock_receiver)(mock_receiver.state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF
    assert state.attributes.get("source") is None

    # Receivers resume their previous input on power-on, so the retained
    # source becomes visible again once a power-on report arrives.
    mock_receiver.state.power = True
    _state_callback(mock_receiver)(mock_receiver.state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.ON
    assert state.attributes["source"] == "HDMI 1"


async def test_media_player_already_disconnected_at_load(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test a receiver lost before entity load schedules a reload."""
    mock_config_entry.add_to_hass(hass)
    mock_receiver.connected = False

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        await _setup_integration(hass, mock_config_entry, mock_receiver)

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == "unavailable"
        mock_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_media_player_unavailable_on_disconnect_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loss triggers one reload attempt and later state restores the entity."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        _state_callback(mock_receiver)(None)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == "unavailable"
        assert "Connection to the Tonewinner receiver was lost" in caplog.text
        mock_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)

        # A repeated disconnect notification must not schedule another reload.
        _state_callback(mock_receiver)(None)
        await hass.async_block_till_done()
        mock_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)

    _state_callback(mock_receiver)(mock_receiver.state)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF
    assert "Connection to the Tonewinner receiver was restored" in caplog.text


@pytest.mark.parametrize(
    ("service", "method", "payload"),
    [
        ("turn_on", "power_on", {}),
        ("turn_off", "power_off", {}),
        ("volume_set", "set_volume", {"volume_level": 0.5}),
        ("volume_up", "volume_up", {}),
        ("volume_down", "volume_down", {}),
        ("volume_mute", "mute_on", {"is_volume_muted": True}),
        ("select_source", "select_source", {"source": "HDMI 1"}),
        ("select_sound_mode", "select_sound_mode", {"sound_mode": "Stereo"}),
    ],
    ids=[
        "on",
        "off",
        "volume",
        "up",
        "down",
        "mute",
        "source",
        "sound_mode",
    ],
)
async def test_media_player_command_failure_raises_ha_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    service: str,
    method: str,
    payload: dict[str, float | bool | str],
) -> None:
    """Test receiver I/O failures surface as Home Assistant errors."""
    mock_config_entry.add_to_hass(hass)
    await _setup_integration(hass, mock_config_entry, mock_receiver)

    getattr(mock_receiver, method).side_effect = ConnectionError("link down")

    with pytest.raises(HomeAssistantError, match="link down"):
        await _call_media_player_service(hass, service, **payload)


def test_sound_mode_codes_prefer_canonical() -> None:
    """Test duplicate labels keep the canonical code over firmware misspellings."""
    assert SOUND_MODES["Direct"] == "DIRECT"
    assert SOUND_MODES["All Stereo"] == "ALLSTEREO"


@pytest.mark.parametrize(
    ("source_name", "audio_source", "expected"),
    [
        ("HDMI 1", None, "HDMI 1"),
        ("hdmi 1", None, "HDMI 1"),
        ("HD1", None, "HDMI 1"),
        ("eARC/ARC", None, "HDMI eARC"),
        ("Mystery Input", "HD1", "HDMI 1"),
        ("Mystery Input", None, "Mystery Input"),
    ],
    ids=[
        "exact_name",
        "case_insensitive_name",
        "code",
        "firmware_earc_label",
        "audio_source_fallback",
        "passthrough",
    ],
)
def test_media_player_resolve_source(
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    source_name: str,
    audio_source: str | None,
    expected: str | None,
) -> None:
    """Test resolving device-reported source names to display names."""
    mock_config_entry.runtime_data = mock_receiver

    entity = TonewinnerMediaPlayer(mock_config_entry)

    assert entity._resolve_source(source_name, audio_source) == expected
