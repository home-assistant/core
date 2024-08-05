"""Test the motionEye camera."""

from asyncio import AbstractEventLoop
from collections.abc import Callable
import copy
from typing import cast
from unittest.mock import AsyncMock, Mock, call

from aiohttp import web
from aiohttp.test_utils import TestServer
from aiohttp.web_exceptions import HTTPBadGateway
from motioneye_client.client import (
    MotionEyeClientError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientURLParseError,
)
from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_MOTION_DETECTION,
    KEY_NAME,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
    KEY_TEXT_OVERLAY_LEFT,
    KEY_TEXT_OVERLAY_RIGHT,
    KEY_TEXT_OVERLAY_TIMESTAMP,
    KEY_VIDEO_STREAMING,
)
import pytest
import voluptuous as vol

from homeassistant.components.camera import async_get_image, async_get_mjpeg_stream
from homeassistant.components.motioneye import get_motioneye_device_identifier
from homeassistant.components.motioneye.const import (
    CONF_ACTION,
    CONF_STREAM_URL_TEMPLATE,
    CONF_SURVEILLANCE_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MOTIONEYE_MANUFACTURER,
    SERVICE_ACTION,
    SERVICE_SET_TEXT_OVERLAY,
    SERVICE_SNAPSHOT,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from . import (
    TEST_CAMERA,
    TEST_CAMERA_DEVICE_IDENTIFIER,
    TEST_CAMERA_ENTITY_ID,
    TEST_CAMERA_ID,
    TEST_CAMERA_NAME,
    TEST_CAMERAS,
    TEST_CONFIG_ENTRY_ID,
    TEST_SURVEILLANCE_USERNAME,
    create_mock_motioneye_client,
    create_mock_motioneye_config_entry,
    setup_mock_motioneye_config_entry,
)

from tests.common import async_fire_time_changed


@pytest.fixture
def aiohttp_server(
    event_loop: AbstractEventLoop,
    aiohttp_server: Callable[[], TestServer],
    socket_enabled: None,
) -> Callable[[], TestServer]:
    """Return aiohttp_server and allow opening sockets."""
    return aiohttp_server


async def test_setup_camera(hass: HomeAssistant) -> None:
    """Test a basic camera."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "streaming"
    assert entity_state.attributes.get("friendly_name") == TEST_CAMERA_NAME


async def test_setup_camera_auth_fail(hass: HomeAssistant) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_client_login = AsyncMock(side_effect=MotionEyeClientInvalidAuthError)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_client_error(hass: HomeAssistant) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_client_login = AsyncMock(side_effect=MotionEyeClientError)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_empty_data(hass: HomeAssistant) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_get_cameras = AsyncMock(return_value={})
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_bad_data(hass: HomeAssistant) -> None:
    """Test bad camera data."""
    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    del cameras[KEY_CAMERAS][0][KEY_NAME]

    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_without_streaming(hass: HomeAssistant) -> None:
    """Test a camera without streaming enabled."""
    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_VIDEO_STREAMING] = False

    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(hass, client=client)
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unavailable"


async def test_setup_camera_new_data_same(hass: HomeAssistant) -> None:
    """Test a data refresh with the same data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_new_data_camera_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a data refresh with a removed camera."""

    client = create_mock_motioneye_client()
    config_entry = await setup_mock_motioneye_config_entry(hass, client=client)

    # Create some random old devices/entity_ids and ensure they get cleaned up.
    old_device_id = "old-device-id"
    old_entity_unique_id = "old-entity-unique_id"
    old_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, old_device_id)}
    )
    entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="camera",
        unique_id=old_entity_unique_id,
        config_entry=config_entry,
        device_id=old_device.id,
    )

    await hass.async_block_till_done()
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert device_registry.async_get_device(identifiers={TEST_CAMERA_DEVICE_IDENTIFIER})

    client.async_get_cameras = AsyncMock(return_value={KEY_CAMERAS: []})
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert not device_registry.async_get_device(
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER}
    )
    assert not device_registry.async_get_device(identifiers={(DOMAIN, old_device_id)})
    assert not entity_registry.async_get_entity_id(
        DOMAIN, "camera", old_entity_unique_id
    )


async def test_setup_camera_new_data_error(hass: HomeAssistant) -> None:
    """Test a data refresh that fails."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    client.async_get_cameras = AsyncMock(side_effect=MotionEyeClientError)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unavailable"


async def test_setup_camera_new_data_without_streaming(hass: HomeAssistant) -> None:
    """Test a data refresh without streaming."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "streaming"

    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_VIDEO_STREAMING] = False
    client.async_get_cameras = AsyncMock(return_value=cameras)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unavailable"


async def test_unload_camera(hass: HomeAssistant) -> None:
    """Test unloading camera."""
    client = create_mock_motioneye_client()
    entry = await setup_mock_motioneye_config_entry(hass, client=client)
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert not client.async_client_close.called
    await hass.config_entries.async_unload(entry.entry_id)
    assert client.async_client_close.called


async def test_get_still_image_from_camera(
    aiohttp_server: Callable[[], TestServer], hass: HomeAssistant
) -> None:
    """Test getting a still image."""

    image_handler = AsyncMock(return_value="")

    app = web.Application()
    app.add_routes(
        [
            web.get(
                "/foo",
                image_handler,
            )
        ]
    )

    server = await aiohttp_server(app)
    client = create_mock_motioneye_client()
    client.get_camera_snapshot_url = Mock(
        return_value=f"http://127.0.0.1:{server.port}/foo"
    )
    config_entry = create_mock_motioneye_config_entry(
        hass,
        data={
            CONF_URL: f"http://127.0.0.1:{server.port}",
            CONF_SURVEILLANCE_USERNAME: TEST_SURVEILLANCE_USERNAME,
        },
    )

    await setup_mock_motioneye_config_entry(
        hass, config_entry=config_entry, client=client
    )
    await hass.async_block_till_done()

    # It won't actually get a stream from the dummy handler, so just catch
    # the expected exception, then verify the right handler was called.
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, TEST_CAMERA_ENTITY_ID, timeout=1)
    assert image_handler.called


async def test_get_stream_from_camera(
    aiohttp_server: Callable[[], TestServer], hass: HomeAssistant
) -> None:
    """Test getting a stream."""

    stream_handler = AsyncMock(return_value="")
    app = web.Application()
    app.add_routes([web.get("/", stream_handler)])
    stream_server = await aiohttp_server(app)

    client = create_mock_motioneye_client()
    client.get_camera_stream_url = Mock(
        return_value=f"http://127.0.0.1:{stream_server.port}/"
    )
    config_entry = create_mock_motioneye_config_entry(
        hass,
        data={
            CONF_URL: f"http://127.0.0.1:{stream_server.port}",
            # The port won't be used as the client is a mock.
            CONF_SURVEILLANCE_USERNAME: TEST_SURVEILLANCE_USERNAME,
        },
    )
    cameras = copy.deepcopy(TEST_CAMERAS)
    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(
        hass, config_entry=config_entry, client=client
    )
    await hass.async_block_till_done()

    # It won't actually get a stream from the dummy handler, so just catch
    # the expected exception, then verify the right handler was called.
    with pytest.raises(HTTPBadGateway):
        await async_get_mjpeg_stream(
            hass, cast(web.Request, None), TEST_CAMERA_ENTITY_ID
        )
    assert stream_handler.called


async def test_state_attributes(hass: HomeAssistant) -> None:
    """Test state attributes are set correctly."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.attributes.get("brand") == MOTIONEYE_MANUFACTURER
    assert entity_state.attributes.get("motion_detection")

    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_MOTION_DETECTION] = False
    client.async_get_cameras = AsyncMock(return_value=cameras)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert not entity_state.attributes.get("motion_detection")


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify device information includes expected details."""
    entry = await setup_mock_motioneye_config_entry(hass)

    device_identifier = get_motioneye_device_identifier(entry.entry_id, TEST_CAMERA_ID)

    device = device_registry.async_get_device(identifiers={device_identifier})
    assert device
    assert device.config_entries == {TEST_CONFIG_ENTRY_ID}
    assert device.identifiers == {device_identifier}
    assert device.manufacturer == MOTIONEYE_MANUFACTURER
    assert device.model == MOTIONEYE_MANUFACTURER
    assert device.name == TEST_CAMERA_NAME

    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_CAMERA_ENTITY_ID in entities_from_device


async def test_camera_option_stream_url_template(
    aiohttp_server: Callable[[], TestServer], hass: HomeAssistant
) -> None:
    """Verify camera with a stream URL template option."""
    client = create_mock_motioneye_client()

    stream_handler = AsyncMock(return_value="")
    app = web.Application()
    app.add_routes([web.get(f"/{TEST_CAMERA_NAME}/{TEST_CAMERA_ID}", stream_handler)])
    stream_server = await aiohttp_server(app)

    client = create_mock_motioneye_client()

    config_entry = create_mock_motioneye_config_entry(
        hass,
        data={
            CONF_URL: f"http://127.0.0.1:{stream_server.port}",
            # The port won't be used as the client is a mock.
            CONF_SURVEILLANCE_USERNAME: TEST_SURVEILLANCE_USERNAME,
        },
        options={
            CONF_STREAM_URL_TEMPLATE: (
                f"http://127.0.0.1:{stream_server.port}/{{{{ name }}}}/{{{{ id }}}}"
            )
        },
    )

    await setup_mock_motioneye_config_entry(
        hass, config_entry=config_entry, client=client
    )
    await hass.async_block_till_done()

    # It won't actually get a stream from the dummy handler, so just catch
    # the expected exception, then verify the right handler was called.
    with pytest.raises(HTTPBadGateway):
        await async_get_mjpeg_stream(hass, Mock(), TEST_CAMERA_ENTITY_ID)
    assert AsyncMock.called
    assert not client.get_camera_stream_url.called


async def test_get_stream_from_camera_with_broken_host(
    aiohttp_server: Callable[[], TestServer], hass: HomeAssistant
) -> None:
    """Test getting a stream with a broken URL (no host)."""

    client = create_mock_motioneye_client()
    config_entry = create_mock_motioneye_config_entry(hass, data={CONF_URL: "http://"})
    client.get_camera_stream_url = Mock(side_effect=MotionEyeClientURLParseError)

    await setup_mock_motioneye_config_entry(
        hass, config_entry=config_entry, client=client
    )
    await hass.async_block_till_done()
    with pytest.raises(HTTPBadGateway):
        await async_get_mjpeg_stream(hass, Mock(), TEST_CAMERA_ENTITY_ID)


async def test_set_text_overlay_bad_extra_key(hass: HomeAssistant) -> None:
    """Test text overlay with incorrect input data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID, "extra_key": "foo"}
    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)


async def test_set_text_overlay_bad_entity_identifier(hass: HomeAssistant) -> None:
    """Test text overlay with bad entity identifier."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_ENTITY_ID: "some random string",
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }

    client.reset_mock()
    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)


async def test_set_text_overlay_bad_empty(hass: HomeAssistant) -> None:
    """Test text overlay with incorrect input data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, {})


async def test_set_text_overlay_bad_no_left_or_right(hass: HomeAssistant) -> None:
    """Test text overlay with incorrect input data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID}
    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)


async def test_set_text_overlay_good(hass: HomeAssistant) -> None:
    """Test a working text overlay."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    custom_left_text = "one\ntwo\nthree"
    custom_right_text = "four\nfive\nsix"
    data = {
        ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_CUSTOM_TEXT,
        KEY_TEXT_OVERLAY_RIGHT: KEY_TEXT_OVERLAY_CUSTOM_TEXT,
        KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT: custom_left_text,
        KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT: custom_right_text,
    }
    client.async_get_camera = AsyncMock(return_value=copy.deepcopy(TEST_CAMERA))

    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert client.async_get_camera.called

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_TEXT_OVERLAY_LEFT] = KEY_TEXT_OVERLAY_CUSTOM_TEXT
    expected_camera[KEY_TEXT_OVERLAY_RIGHT] = KEY_TEXT_OVERLAY_CUSTOM_TEXT
    expected_camera[KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT] = "one\\ntwo\\nthree"
    expected_camera[KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT] = "four\\nfive\\nsix"
    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_set_text_overlay_good_entity_id(hass: HomeAssistant) -> None:
    """Test a working text overlay with entity_id."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }
    client.async_get_camera = AsyncMock(return_value=copy.deepcopy(TEST_CAMERA))
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert client.async_get_camera.called

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_TEXT_OVERLAY_LEFT] = KEY_TEXT_OVERLAY_TIMESTAMP
    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_set_text_overlay_bad_device(hass: HomeAssistant) -> None:
    """Test a working text overlay."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_DEVICE_ID: "not a device",
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }
    client.reset_mock()
    client.async_get_camera = AsyncMock(return_value=copy.deepcopy(TEST_CAMERA))
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert not client.async_get_camera.called
    assert not client.async_set_camera.called


async def test_set_text_overlay_no_such_camera(hass: HomeAssistant) -> None:
    """Test a working text overlay."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }
    client.reset_mock()
    client.async_get_camera = AsyncMock(return_value={})
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert not client.async_set_camera.called


async def test_request_action(hass: HomeAssistant) -> None:
    """Test requesting an action."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
        CONF_ACTION: "foo",
    }
    await hass.services.async_call(DOMAIN, SERVICE_ACTION, data)
    await hass.async_block_till_done()
    assert client.async_action.call_args == call(TEST_CAMERA_ID, data[CONF_ACTION])


async def test_request_snapshot(hass: HomeAssistant) -> None:
    """Test requesting a snapshot."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID}

    await hass.services.async_call(DOMAIN, SERVICE_SNAPSHOT, data)
    await hass.async_block_till_done()
    assert client.async_action.call_args == call(TEST_CAMERA_ID, "snapshot")
