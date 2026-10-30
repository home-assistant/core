"""Test the UniFi Protect media_player platform."""

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.typing import WebSocketGenerator
from uiprotect.data import Camera, ChannelQuality, DeviceState, StateType, WSAction
from uiprotect.data.devices import Hotplug
from uiprotect.exceptions import BadRequest, NotAuthorized, StreamError

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntityFeature,
)
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_IDLE,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotSupported
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import patch_ufp_method
from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    init_entry,
    make_public_camera,
    public_device_ws_message,
    public_rtsps_for,
    regenerate_device_ids,
    remove_entities,
)

ENTITY_ID = "media_player.test_camera_speaker"

_PLAYBACK_FEATURES = (
    MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)
_ALL_FEATURES = (
    _PLAYBACK_FEATURES
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

type SpeakerSetup = Callable[[], Coroutine[Any, Any, tuple[MockUFPFixture, Mock]]]

BOTH_MODES = pytest.mark.parametrize(
    "setup_fixture",
    [
        pytest.param("setup_hybrid_speaker", id="hybrid"),
        pytest.param("setup_public_only_speaker", id="public_only"),
    ],
)


def _make_public_speaker(camera: Camera) -> Mock:
    """Build a public camera the camera platform can also enumerate."""
    public = make_public_camera(camera)
    public.rtsps_streams = public_rtsps_for(ChannelQuality.HIGH)
    return public


@pytest.fixture(name="setup_hybrid_speaker")
def setup_hybrid_speaker_fixture(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> SpeakerSetup:
    """Return a callable setting up the hybrid entry with a doorbell speaker."""

    async def _setup() -> tuple[MockUFPFixture, Mock]:
        await init_entry(hass, ufp, [doorbell, unadopted_camera])
        return ufp, ufp.api.public_bootstrap.cameras[doorbell.id]

    return _setup


@pytest.fixture(name="setup_public_only_speaker")
def setup_public_only_speaker_fixture(
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    doorbell: Camera,
) -> SpeakerSetup:
    """Return a callable setting up the API-key-only entry with a doorbell speaker."""

    async def _setup() -> tuple[MockUFPFixture, Mock]:
        public = _make_public_speaker(doorbell)
        ufp_public_only.api.public_bootstrap.cameras = {doorbell.id: public}
        await setup_public_only()
        return ufp_public_only, public

    return _setup


@pytest.fixture(name="speaker")
async def speaker_fixture(
    request: pytest.FixtureRequest, setup_fixture: str
) -> tuple[MockUFPFixture, Mock]:
    """Set up the mode named by ``setup_fixture`` and return its public camera."""
    setup: SpeakerSetup = request.getfixturevalue(setup_fixture)
    return await setup()


async def _play(hass: HomeAssistant, media_id: str = "http://example.com/test.mp3"):
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_id": media_id,
            "media_content_type": "music",
        },
        blocking=True,
    )


async def test_media_player_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test removing and re-adopting a camera finds its public object again."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)
    await remove_entities(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 0, 0)
    await adopt_devices(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE

    await _play(hass)
    ufp.api.public_bootstrap.cameras[doorbell.id].play_audio.assert_awaited_once()


async def test_media_player_adopted_at_runtime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A speaker camera adopted while running gets the speaker unique ID and name."""

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 0, 0)

    doorbell._api = ufp.api
    await adopt_devices(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    entity = entity_registry.async_get("media_player.test_camera_speaker")
    assert entity
    assert entity.unique_id == f"{doorbell.mac}_speaker"
    state = hass.states.get("media_player.test_camera_speaker")
    assert state
    assert state.name == "Test Camera Speaker"


@pytest.mark.parametrize(
    ("setup_fixture", "features", "volume", "model", "sw_version"),
    [
        # Device info comes from the private camera in hybrid.
        pytest.param(
            "setup_hybrid_speaker",
            _ALL_FEATURES,
            1.0,
            "G4 Instant",
            "4.47.13",
            id="hybrid",
        ),
        pytest.param(
            "setup_public_only_speaker",
            _PLAYBACK_FEATURES,
            None,
            "UVC G4 Instant",
            None,
            id="public_only",
        ),
    ],
)
async def test_media_player_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    speaker: tuple[MockUFPFixture, Mock],
    features: MediaPlayerEntityFeature,
    volume: float | None,
    model: str,
    sw_version: str | None,
) -> None:
    """Volume features and state exist only with a private camera."""
    _, public = speaker
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity
    assert entity.unique_id == f"{public.mac}_speaker"
    device = device_registry.async_get(entity.device_id)
    assert device
    assert device.model == model
    assert device.sw_version == sw_version

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_IDLE
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == features
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == "music"
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == volume


@pytest.mark.parametrize(
    ("has_speaker", "removable", "count"),
    [
        pytest.param(True, False, 1, id="speaker"),
        pytest.param(False, True, 1, id="removable_speaker"),
        pytest.param(False, False, 0, id="no_speaker"),
    ],
)
async def test_media_player_hybrid_private_gate(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    has_speaker: bool,
    removable: bool,
    count: int,
) -> None:
    """Hybrid keeps creating speakers from the private camera's flags."""
    camera.has_speaker = has_speaker
    camera.feature_flags.hotplug = Hotplug(audio=True) if removable else None

    await init_entry(hass, ufp, [camera])

    assert_entity_counts(hass, Platform.MEDIA_PLAYER, count, count)


@pytest.mark.parametrize(("has_speaker", "count"), [(True, 2), (False, 0)])
async def test_media_player_public_only_speaker_gate(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    camera: Camera,
    doorbell: Camera,
    has_speaker: bool,
    count: int,
) -> None:
    """Public-only creates a speaker per public camera with one, also when added."""
    regenerate_device_ids(doorbell)
    camera.feature_flags.has_speaker = has_speaker
    doorbell.feature_flags.has_speaker = has_speaker
    pb = ufp_public_only.api.public_bootstrap
    pb.cameras = {camera.id: _make_public_speaker(camera)}
    await setup_public_only()

    added = _make_public_speaker(doorbell)
    pb.cameras[doorbell.id] = added
    ufp_public_only.devices_ws_subscription(
        public_device_ws_message(added, action=WSAction.ADD)
    )
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.MEDIA_PLAYER, count, count)


async def _set_private_volume(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, volume: int
) -> Camera:
    """Push a private camera update with ``volume`` (no ``speaker_volume``)."""
    new_camera = doorbell.model_copy()
    new_camera.speaker_settings = doorbell.speaker_settings.model_copy()
    new_camera.speaker_settings.speaker_volume = None
    new_camera.speaker_settings.volume = volume
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(Mock(changed_data={}, new_obj=new_camera))
    await hass.async_block_till_done()
    return new_camera


async def test_media_player_hybrid_volume_state(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    setup_hybrid_speaker: SpeakerSetup,
) -> None:
    """Hybrid volume is read from the private camera."""
    await setup_hybrid_speaker()

    # Playback state comes from the public camera only.
    doorbell.talkback_stream = Mock(is_running=True)
    await _set_private_volume(hass, ufp, doorbell, 30)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.3
    assert state.state == STATE_IDLE


@pytest.mark.parametrize(
    ("service", "data", "expected"),
    [
        pytest.param("volume_set", {"volume_level": 0.5}, 50, id="volume_set"),
        # One default step (0.1) up from the private camera's 30.
        pytest.param("volume_up", {}, 40, id="volume_up"),
    ],
)
async def test_media_player_hybrid_set_volume(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    setup_hybrid_speaker: SpeakerSetup,
    service: str,
    data: dict[str, Any],
    expected: int,
) -> None:
    """Hybrid volume is written to the private camera."""
    await setup_hybrid_speaker()
    camera = await _set_private_volume(hass, ufp, doorbell, 30)

    with patch_ufp_method(
        camera, "set_speaker_volume", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "media_player", service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
        )

    mock_method.assert_awaited_once_with(expected)


async def test_media_player_hybrid_set_volume_error(
    hass: HomeAssistant, doorbell: Camera, setup_hybrid_speaker: SpeakerSetup
) -> None:
    """A rejected volume change surfaces as a translated error."""
    await setup_hybrid_speaker()

    with (
        patch_ufp_method(
            doorbell,
            "set_speaker_volume",
            new_callable=AsyncMock,
            side_effect=BadRequest("volume rejected"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {ATTR_ENTITY_ID: ENTITY_ID, "volume_level": 0.5},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_error"


@pytest.mark.parametrize(
    ("service", "data"),
    [("volume_set", {"volume_level": 0.5}), ("volume_up", {})],
)
async def test_media_player_public_only_no_volume(
    hass: HomeAssistant,
    setup_public_only_speaker: SpeakerSetup,
    service: str,
    data: dict[str, Any],
) -> None:
    """Public-only rejects volume actions: the public API has no speaker volume."""
    await setup_public_only_speaker()

    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            "media_player",
            service,
            {ATTR_ENTITY_ID: ENTITY_ID, **data},
            blocking=True,
        )


def _start_stream_on_play(public: Mock) -> None:
    """Make ``play_audio`` leave a running talkback stream, as the library does."""

    async def _play_audio(*args: Any, **kwargs: Any) -> None:
        public.talkback_stream = Mock(is_running=True)

    public.play_audio.side_effect = _play_audio


@BOTH_MODES
async def test_media_player_playing_state(
    hass: HomeAssistant, speaker: tuple[MockUFPFixture, Mock]
) -> None:
    """The state is playing while the public talkback stream runs."""
    _, public = speaker
    _start_stream_on_play(public)
    states: list[str] = []

    async def _wait() -> None:
        states.append(hass.states.get(ENTITY_ID).state)
        public.talkback_stream.is_running = False

    public.wait_until_audio_completes.side_effect = _wait

    await _play(hass)

    assert states == [STATE_PLAYING]
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE


@BOTH_MODES
@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda public: setattr(public, "has_speaker", False),
            id="no_speaker",
        ),
        pytest.param(
            lambda public: setattr(public, "state", DeviceState.DISCONNECTED),
            id="disconnected",
        ),
    ],
)
async def test_media_player_availability(
    hass: HomeAssistant,
    speaker: tuple[MockUFPFixture, Mock],
    mutate: Callable[[Mock], None],
) -> None:
    """The speaker needs a reachable public camera that has a speaker."""
    ufp, public = speaker
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE

    mutate(public)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_media_player_hybrid_waits_for_public_mirror(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """A hybrid speaker without a public mirror is unavailable until it arrives."""
    ufp.api.update_public = AsyncMock()

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    public = _make_public_speaker(doorbell)
    ufp.api.public_bootstrap.cameras = {doorbell.id: public}
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_IDLE
    await _play(hass)
    public.play_audio.assert_awaited_once()


@BOTH_MODES
async def test_media_player_unavailable_when_public_removed(
    hass: HomeAssistant, speaker: tuple[MockUFPFixture, Mock]
) -> None:
    """The speaker is unavailable while its public camera is missing."""
    ufp, public = speaker

    del ufp.api.public_bootstrap.cameras[public.id]
    msg = public_device_ws_message(public, action=WSAction.REMOVE)
    msg.new_obj = None
    msg.old_obj = public
    ufp.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_media_player_hybrid_ignores_private_connection(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    setup_hybrid_speaker: SpeakerSetup,
) -> None:
    """Hybrid availability follows the public camera, not the private one."""
    await setup_hybrid_speaker()

    new_camera = doorbell.model_copy()
    new_camera.state = StateType.DISCONNECTED
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(Mock(changed_data={}, new_obj=new_camera))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_IDLE


@BOTH_MODES
async def test_media_player_stop_while_playing(
    hass: HomeAssistant, speaker: tuple[MockUFPFixture, Mock]
) -> None:
    """Stopping running audio goes to the public camera and writes idle."""
    _, public = speaker
    _start_stream_on_play(public)
    waiting = asyncio.Event()
    release = asyncio.Event()

    async def _wait() -> None:
        waiting.set()
        await release.wait()

    async def _stop_audio() -> None:
        public.talkback_stream.is_running = False

    public.wait_until_audio_completes.side_effect = _wait
    public.stop_audio.side_effect = _stop_audio

    play = hass.async_create_task(_play(hass))
    await waiting.wait()
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    # Written by the stop itself; playback is still awaiting completion.
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE
    public.stop_audio.assert_awaited_once()

    release.set()
    await play


@BOTH_MODES
async def test_media_player_stop_when_idle(
    hass: HomeAssistant, speaker: tuple[MockUFPFixture, Mock]
) -> None:
    """Stopping without running audio does not call the library."""
    _, public = speaker
    public.talkback_stream = Mock(is_running=False)

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    public.stop_audio.assert_not_awaited()


@BOTH_MODES
@pytest.mark.parametrize(
    "media_id", ["http://example.com/test.mp3", "media-source://some_source/some_id"]
)
async def test_media_player_play(
    hass: HomeAssistant,
    speaker: tuple[MockUFPFixture, Mock],
    media_id: str,
) -> None:
    """Playback goes to the public camera."""
    _, public = speaker

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=Mock(url="http://example.com/test.mp3"),
    ):
        await _play(hass, media_id)

    public.play_audio.assert_awaited_once_with(
        "http://example.com/test.mp3", blocking=False
    )
    public.wait_until_audio_completes.assert_awaited_once()


async def test_media_player_play_stops_running_audio(
    hass: HomeAssistant, setup_hybrid_speaker: SpeakerSetup
) -> None:
    """Running audio is stopped before new audio starts."""
    _, public = await setup_hybrid_speaker()
    public.talkback_stream = Mock(is_running=True)
    calls: list[str] = []
    public.stop_audio.side_effect = lambda: calls.append("stop")
    public.play_audio.side_effect = lambda *args, **kwargs: calls.append("play")

    await _play(hass)

    assert calls == ["stop", "play"]


async def test_media_player_play_invalid(
    hass: HomeAssistant, setup_hybrid_speaker: SpeakerSetup
) -> None:
    """Test media_player entity test play_media, not music."""
    _, public = await setup_hybrid_speaker()

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "media_content_id": "/test.png",
                "media_content_type": "image",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "only_music_supported"
    assert not public.play_audio.called


@BOTH_MODES
@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(StreamError("no session"), "stream_error", id="stream"),
        pytest.param(
            BadRequest("Camera is already playing audio"),
            "command_error",
            id="bad_request",
        ),
        pytest.param(NotAuthorized("denied"), "not_authorized", id="not_authorized"),
    ],
)
async def test_media_player_play_error(
    hass: HomeAssistant,
    speaker: tuple[MockUFPFixture, Mock],
    error: Exception,
    translation_key: str,
) -> None:
    """Library errors while starting playback surface as translated errors."""
    _, public = speaker
    public.play_audio.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _play(hass)

    assert exc_info.value.translation_key == translation_key
    assert not public.wait_until_audio_completes.called
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE


async def test_media_player_play_wait_error(
    hass: HomeAssistant,
    setup_hybrid_speaker: SpeakerSetup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a stream error while waiting for playback raises and resets the state."""
    _, public = await setup_hybrid_speaker()
    _start_stream_on_play(public)

    async def _wait_fails() -> None:
        assert hass.states.get(ENTITY_ID).state == STATE_PLAYING
        public.talkback_stream.is_running = False
        raise StreamError("Audio streaming failed")

    public.wait_until_audio_completes.side_effect = _wait_fails

    with pytest.raises(HomeAssistantError) as exc_info:
        await _play(hass)

    assert exc_info.value.translation_key == "stream_error"
    assert (
        "homeassistant.components.unifiprotect.media_player",
        logging.DEBUG,
        "Error playing audio: Audio streaming failed",
    ) in caplog.record_tuples
    assert hass.states.get(ENTITY_ID).state == STATE_IDLE


async def test_media_player_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_hybrid_speaker: SpeakerSetup,
) -> None:
    """Browsing offers audio media only."""
    await setup_hybrid_speaker()
    root = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="",
        title="Media",
        can_play=False,
        can_expand=True,
    )

    with patch(
        "homeassistant.components.media_source.async_browse_media",
        return_value=root,
    ) as mock_browse:
        client = await hass_ws_client(hass)
        await client.send_json_auto_id(
            {"type": "media_player/browse_media", "entity_id": ENTITY_ID}
        )
        msg = await client.receive_json()

    assert msg["success"]
    content_filter = mock_browse.call_args.kwargs["content_filter"]
    assert content_filter(Mock(media_content_type="audio/mpeg"))
    assert not content_filter(Mock(media_content_type="video/mp4"))
