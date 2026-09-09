"""Tests for the Openhome media player platform."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

from openhomedevice.device import Device
from openhomedevice.exceptions import OpenhomeConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaType,
)
from homeassistant.components.openhome.const import DOMAIN
from homeassistant.components.openhome.services import (
    ATTR_PIN_INDEX,
    SERVICE_INVOKE_PIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import async_poll, setup_integration
from .conftest import TRACK_INFO

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "media_player.friendly_name"

# Each action, the coroutine it drives, and a source type that exposes the
# supported feature it is gated behind.
ACTIONS = [
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {},
        Device.set_standby,
        "Playlist",
        id="turn_on",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {},
        Device.set_standby,
        "Playlist",
        id="turn_off",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {},
        Device.play,
        "Playlist",
        id="media_play",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {},
        Device.pause,
        "Playlist",
        id="media_pause",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {},
        Device.stop,
        "Radio",
        id="media_stop",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {},
        Device.skip,
        "Playlist",
        id="media_next_track",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {},
        Device.skip,
        "Playlist",
        id="media_previous_track",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {},
        Device.increase_volume,
        "Playlist",
        id="volume_up",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {},
        Device.decrease_volume,
        "Playlist",
        id="volume_down",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        Device.set_volume,
        "Playlist",
        id="volume_set",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: True},
        Device.set_mute,
        "Playlist",
        id="volume_mute",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "Playlist"},
        Device.set_source,
        "Playlist",
        id="select_source",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://localhost/track.flac",
        },
        Device.play_media,
        "Playlist",
        id="play_media",
    ),
]


@pytest.fixture(autouse=True)
def media_proxy_token() -> Generator[None]:
    """Freeze the media proxy token, which otherwise varies per run."""
    with patch("secrets.token_hex", return_value="mock_token"):
        yield


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the media player platform."""
    return [Platform.MEDIA_PLAYER]


async def setup_media_player(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Load the media player platform and poll once."""
    await setup_integration(hass, mock_config_entry)

    # Supported features are only set once the device has been polled.
    await async_poll(hass)


@pytest.mark.parametrize(
    ("domain", "service", "data", "method", "source_type"), ACTIONS
)
async def test_action_error_is_raised(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    domain: str,
    service: str,
    data: dict[str, Any],
    method: Callable[..., Any],
    source_type: str,
) -> None:
    """Test every action raises when the device rejects the request."""
    # The feature each action is gated behind depends on the selected source.
    mock_device.source.return_value = {
        "index": 0,
        "name": source_type,
        "type": source_type,
    }

    await setup_media_player(hass, mock_config_entry)

    mocked = getattr(mock_device, method.__name__)
    mocked.side_effect = OpenhomeConnectionError("no route to host")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
        )

    # The message is keyed on the service name, so each action reports its own.
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == service
    mocked.assert_awaited()


@pytest.mark.parametrize(
    ("pins_enabled", "translation_key", "await_count"),
    [
        pytest.param(True, SERVICE_INVOKE_PIN, 1, id="pins_supported"),
        pytest.param(False, "pins_not_supported", 0, id="pins_not_supported"),
    ],
)
async def test_invoke_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    pins_enabled: bool,
    translation_key: str,
    await_count: int,
) -> None:
    """Test invoking a pin on a device with and without pin support."""
    mock_device.pins_enabled = pins_enabled

    await setup_media_player(hass, mock_config_entry)
    mock_device.invoke_pin.side_effect = OpenhomeConnectionError("no route to host")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INVOKE_PIN,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PIN_INDEX: 1},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    assert mock_device.invoke_pin.await_count == await_count


async def test_media_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the media player is set up from the device state."""
    mock_device.track_info.return_value = TRACK_INFO

    await setup_media_player(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_becomes_unavailable_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed poll logs once, marks the device unavailable and recovers."""
    await setup_media_player(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING

    mock_device.room.side_effect = OpenhomeConnectionError("device unreachable")
    await async_poll(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("device unreachable") == 1

    # A second consecutive failure must not log the same outage again.
    await async_poll(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("device unreachable") == 1

    mock_device.room.side_effect = None
    await async_poll(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING


@pytest.mark.parametrize(
    ("in_standby", "transport_state", "expected_state"),
    [
        pytest.param(True, "Playing", STATE_OFF, id="standby"),
        pytest.param(False, "Paused", STATE_PAUSED, id="paused"),
        pytest.param(False, "Playing", STATE_PLAYING, id="playing"),
        pytest.param(False, "Buffering", STATE_PLAYING, id="buffering"),
        pytest.param(False, "Stopped", STATE_IDLE, id="stopped"),
        # An external source with no transport controls still counts as playing.
        pytest.param(False, "Unknown", STATE_PLAYING, id="external_source"),
    ],
)
async def test_state_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    in_standby: bool,
    transport_state: str,
    expected_state: str,
) -> None:
    """Test the device transport state maps onto the media player state."""
    mock_device.is_in_standby.return_value = in_standby
    mock_device.transport_state.return_value = transport_state

    await setup_media_player(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == expected_state
