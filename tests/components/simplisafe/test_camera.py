"""Define tests for the SimpliSafe camera platform."""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from simplipy.errors import SimplipyError
from simplipy.system.v3 import SystemV3
from simplipy.websocket import WebsocketEvent
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image
from homeassistant.components.simplisafe import _resolve_image_url
from homeassistant.components.simplisafe.coordinator import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

CAMERA_SERIAL = "abc123"
IMAGE_URL_TEMPLATE = (
    "https://remix.us-east-1.prd.cam.simplisafe.com/v1/snapshot"
    "/abc123/6720379/time/1779583826?account=611485993050&region=us-east-1{&width}"
)
CLIP_URL_TEMPLATE = (
    "https://remix.us-east-1.prd.cam.simplisafe.com/v1/clip"
    "/abc123?account=611485993050{&token}"
)
IMAGE_BYTES = b"fake_image_data"

VIDEO_DATA = {
    "vid001": {
        "_links": {
            "snapshot/jpg": {"href": IMAGE_URL_TEMPLATE},
            "download/mp4": {"href": CLIP_URL_TEMPLATE},
            "playback/hls": {"href": "https://example.com/hls"},
        }
    }
}


def _make_motion_event(
    system_id: int = 12345,
    serial: str = CAMERA_SERIAL,
    with_media: bool = True,
) -> WebsocketEvent:
    """Build a camera motion WebsocketEvent."""
    return WebsocketEvent(
        event_cid=1170,
        info="Motion detected",
        system_id=system_id,
        _raw_timestamp=0,
        _video=VIDEO_DATA if with_media else None,
        _vid="vid001" if with_media else None,
        sensor_serial=serial,
    )


def test_resolve_image_url_substitutes_width() -> None:
    """Default width of 720 is substituted into the template."""
    url = "https://example.com/snap?a=1{&width}"
    resolved = _resolve_image_url(url)
    assert "&width=720" in resolved
    assert "{" not in resolved
    assert "}" not in resolved


def test_resolve_image_url_custom_width() -> None:
    """A custom width value is substituted correctly."""
    url = "https://example.com/snap?a=1{&width}"
    resolved = _resolve_image_url(url, width=480)
    assert "&width=480" in resolved
    assert "{" not in resolved


def test_resolve_image_url_strips_remaining_templates() -> None:
    """Any unrecognised URI template placeholders are stripped."""
    url = "https://example.com/snap{&width}{&extra}"
    resolved = _resolve_image_url(url)
    assert "&width=720" in resolved
    assert "{" not in resolved
    assert "}" not in resolved


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_entity_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """An entity is created for the outdoor camera sensor."""
    with (
        patch("homeassistant.components.simplisafe.PLATFORMS", [Platform.CAMERA]),
        patch("random.SystemRandom.getrandbits", return_value=123123123123),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_camera_entity_not_created_for_v2_system(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    system_v3: SystemV3,
) -> None:
    """No camera entity is created when the system reports version 2."""
    with patch.object(
        type(system_v3), "version", new_callable=PropertyMock, return_value=2
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("camera.backyard_outdoor_camera") is None


async def test_outdoor_camera_battery_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    system_v3: SystemV3,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The outdoor camera creates and updates a low-battery binary sensor."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.backyard_outdoor_camera_battery"
    assert hass.states.get(entity_id).state == STATE_OFF

    with patch.object(
        type(system_v3.sensors[CAMERA_SERIAL]),
        "low_battery",
        new_callable=PropertyMock,
        return_value=True,
    ):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_id).state == STATE_ON


async def test_motion_event_with_no_media_leaves_image_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """A motion event without media URLs leaves no image available."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event(with_media=False))
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.backyard_outdoor_camera")


async def test_motion_event_wrong_system_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """A motion event from a different system does not make an image available."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event(system_id=99999))
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.backyard_outdoor_camera")


async def test_motion_event_wrong_serial_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """A motion event for a different camera serial does not make an image available."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event(serial="other_serial"))
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.backyard_outdoor_camera")


async def test_async_camera_image_raises_before_motion(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """async_get_image raises HomeAssistantError when no motion has occurred yet."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.backyard_outdoor_camera")


async def test_async_camera_image_returns_bytes_after_motion(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
) -> None:
    """async_camera_image returns image bytes with the resolved URL."""
    api.async_media = AsyncMock(return_value=IMAGE_BYTES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    image = await async_get_image(hass, "camera.backyard_outdoor_camera")
    assert image.content == IMAGE_BYTES

    # The URL passed to async_media must not contain unresolved URI templates.
    url_used = api.async_media.call_args[0][0]
    assert "{" not in url_used
    assert "}" not in url_used
    assert "&width=720" in url_used


async def test_async_camera_image_uses_requested_width(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
) -> None:
    """async_camera_image passes the requested width to the URL resolver."""
    api.async_media = AsyncMock(return_value=IMAGE_BYTES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    await async_get_image(hass, "camera.backyard_outdoor_camera", width=480)

    url_used = api.async_media.call_args[0][0]
    assert "&width=480" in url_used


async def test_async_camera_image_raises_on_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
) -> None:
    """async_get_image raises HomeAssistantError when the API call fails."""
    api.async_media = AsyncMock(side_effect=SimplipyError("boom"))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.backyard_outdoor_camera")
