"""Define tests for the SimpliSafe camera platform."""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from simplipy.errors import SimplipyError
from simplipy.websocket import WebsocketEvent

from homeassistant.components.camera import async_get_image
from homeassistant.components.simplisafe import (
    DOMAIN,
    _resolve_clip_url,
    _resolve_image_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

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
CLIP_BYTES = b"fake_clip_data"

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


# ---------------------------------------------------------------------------
# URL resolution unit tests (no HA setup required)
# ---------------------------------------------------------------------------


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


def test_resolve_clip_url_strips_templates() -> None:
    """URI template placeholders are stripped from clip URLs."""
    url = "https://example.com/clip{&token}"
    resolved = _resolve_clip_url(url)
    assert "{" not in resolved
    assert "}" not in resolved
    assert "example.com/clip" in resolved


# ---------------------------------------------------------------------------
# Camera entity creation
# ---------------------------------------------------------------------------


async def test_camera_entity_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """An entity is created for the outdoor camera sensor."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("camera.backyard_outdoor_camera")
    assert state is not None


async def test_camera_entity_not_created_for_v2_system(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    system_v3,
) -> None:
    """No camera entity is created when the system reports version 2."""
    with patch.object(
        type(system_v3), "version", new_callable=PropertyMock, return_value=2
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("camera.backyard_outdoor_camera") is None


# ---------------------------------------------------------------------------
# Websocket motion event handling
# ---------------------------------------------------------------------------


async def test_motion_event_caches_media_urls(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Motion event stores media URLs on the SimpliSafe data object."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    simplisafe = config_entry.runtime_data
    assert CAMERA_SERIAL in simplisafe.camera_media_urls
    assert "image_url" in simplisafe.camera_media_urls[CAMERA_SERIAL]
    assert "clip_url" in simplisafe.camera_media_urls[CAMERA_SERIAL]


async def test_motion_event_with_no_media_does_not_cache(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Motion event without media URLs leaves the cache empty."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event(with_media=False))
    await hass.async_block_till_done()

    simplisafe = config_entry.runtime_data
    assert CAMERA_SERIAL not in simplisafe.camera_media_urls


async def test_motion_event_wrong_system_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Motion event from a different system does not populate the cache."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event(system_id=99999))
    await hass.async_block_till_done()

    simplisafe = config_entry.runtime_data
    assert CAMERA_SERIAL not in simplisafe.camera_media_urls


async def test_motion_event_wrong_serial_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Motion event for a different camera serial does not populate this camera's cache."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event(serial="other_serial"))
    await hass.async_block_till_done()

    simplisafe = config_entry.runtime_data
    assert CAMERA_SERIAL not in simplisafe.camera_media_urls


# ---------------------------------------------------------------------------
# async_camera_image
# ---------------------------------------------------------------------------


async def test_async_camera_image_returns_none_before_motion(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """async_camera_image returns None (HomeAssistantError) when no motion yet."""
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
    """async_camera_image returns None (HomeAssistantError) on SimplipyError."""
    api.async_media = AsyncMock(side_effect=SimplipyError("boom"))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.backyard_outdoor_camera")


# ---------------------------------------------------------------------------
# capture_motion_image service
# ---------------------------------------------------------------------------


async def test_capture_motion_image_saves_file(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_image writes image bytes to the given path."""
    api.async_media = AsyncMock(return_value=IMAGE_BYTES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("homeassistant.components.simplisafe.Path") as mock_path,
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_image",
            {"device_id": camera_device.id, "filename": "/config/www/test.jpg"},
            blocking=True,
        )

    mock_path.return_value.write_bytes.assert_called_once_with(IMAGE_BYTES)

    # Confirm the URL had no template placeholders.
    url_used = api.async_media.call_args[0][0]
    assert "{" not in url_used
    assert "&width=720" in url_used


async def test_capture_motion_image_custom_width(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_image passes the specified width to the resolved URL."""
    api.async_media = AsyncMock(return_value=IMAGE_BYTES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("homeassistant.components.simplisafe.Path"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_image",
            {
                "device_id": camera_device.id,
                "filename": "/config/www/test.jpg",
                "width": 480,
            },
            blocking=True,
        )

    url_used = api.async_media.call_args[0][0]
    assert "&width=480" in url_used


async def test_capture_motion_image_raises_when_no_motion(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_image raises HomeAssistantError when no motion has occurred."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_image",
            {"device_id": camera_device.id, "filename": "/config/www/test.jpg"},
            blocking=True,
        )


async def test_capture_motion_image_raises_for_disallowed_path(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_image raises HomeAssistantError for a path outside allowed dirs."""
    api.async_media = AsyncMock(return_value=IMAGE_BYTES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_image",
            {"device_id": camera_device.id, "filename": "/etc/passwd"},
            blocking=True,
        )


async def test_capture_motion_image_raises_on_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_image raises HomeAssistantError when the API call fails."""
    api.async_media = AsyncMock(side_effect=SimplipyError("boom"))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_image",
            {"device_id": camera_device.id, "filename": "/config/www/test.jpg"},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# capture_motion_clip service
# ---------------------------------------------------------------------------


async def test_capture_motion_clip_saves_file(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_clip writes clip bytes to the given path."""
    api.async_media = AsyncMock(return_value=CLIP_BYTES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("homeassistant.components.simplisafe.Path") as mock_path,
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_clip",
            {"device_id": camera_device.id, "filename": "/config/www/test.mp4"},
            blocking=True,
        )

    mock_path.return_value.write_bytes.assert_called_once_with(CLIP_BYTES)

    url_used = api.async_media.call_args[0][0]
    assert "{" not in url_used
    assert "}" not in url_used


async def test_capture_motion_clip_raises_when_no_motion(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_clip raises HomeAssistantError when no motion has occurred."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_clip",
            {"device_id": camera_device.id, "filename": "/config/www/test.mp4"},
            blocking=True,
        )


async def test_capture_motion_clip_raises_for_disallowed_path(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_clip raises HomeAssistantError for a path outside allowed dirs."""
    api.async_media = AsyncMock(return_value=CLIP_BYTES)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_clip",
            {"device_id": camera_device.id, "filename": "/etc/passwd"},
            blocking=True,
        )


async def test_capture_motion_clip_raises_on_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
    api: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """capture_motion_clip raises HomeAssistantError when the API call fails."""
    api.async_media = AsyncMock(side_effect=SimplipyError("boom"))

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]
    event_callback(_make_motion_event())
    await hass.async_block_till_done()

    camera_device = device_registry.async_get_device(
        identifiers={(DOMAIN, CAMERA_SERIAL)}
    )
    assert camera_device is not None

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "capture_motion_clip",
            {"device_id": camera_device.id, "filename": "/config/www/test.mp4"},
            blocking=True,
        )
