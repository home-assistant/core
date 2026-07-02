"""Tests for the Notifications for Android TV / Fire TV notify platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from notifications_android_tv.notifications import ConnectError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import camera, image, media_source
from homeassistant.components.nfandroidtv.const import (
    ATTR_BGCOLOR,
    ATTR_DURATION,
    ATTR_FONTSIZE,
    ATTR_IMAGE,
    ATTR_INTERACTIVE,
    ATTR_POSITION,
    ATTR_TRANSPARENCY,
    DOMAIN,
)
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    CONF_NAME,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import NAME

from tests.common import AsyncMock, MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def notify_only() -> AsyncGenerator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.nfandroidtv.PLATFORMS",
        [Platform.NOTIFY],
    ):
        yield


@pytest.mark.usefixtures("mock_notifications_android_tv")
async def test_notify_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the notify platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.freeze_time("1970-01-01T00:00:00+00:00")
async def test_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message."""
    entity_id = "notify.android_tv_fire_tv_1_2_3_4"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MESSAGE: "Hello",
            ATTR_TITLE: "World",
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"

    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World"
    )


async def test_send_message_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message exception."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_notifications_android_tv.send.side_effect = ConnectError

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.android_tv_fire_tv_1_2_3_4",
                ATTR_MESSAGE: "Hello",
                ATTR_TITLE: "World",
            },
            blocking=True,
        )

    assert err.value.translation_key == "notify_connection_error"
    assert err.value.translation_placeholders == {CONF_NAME: NAME}

    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World"
    )


@pytest.mark.freeze_time("1970-01-01T00:00:00+00:00")
async def test_nfandroidtv_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message via nfandroidtv.send_message action."""
    entity_id = "notify.android_tv_fire_tv_1_2_3_4"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MESSAGE: "Hello",
            ATTR_TITLE: "World",
            ATTR_POSITION: "center",
            ATTR_DURATION: {"seconds": 30},
            ATTR_INTERACTIVE: True,
            ATTR_BGCOLOR: "teal",
            ATTR_FONTSIZE: "large",
            ATTR_TRANSPARENCY: "75%",
        },
        blocking=True,
    )

    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello",
        title="World",
        position="center",
        fontsize="large",
        transparency="75%",
        interrupt=True,
        duration=30,
        bkgcolor="teal",
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


@pytest.mark.freeze_time("1970-01-01T00:00:00+00:00")
async def test_nfandroidtv_send_message_camera_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message with camera snapshot via nfandroidtv.send_message action."""
    entity_id = "notify.android_tv_fire_tv_1_2_3_4"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    with (
        patch(
            "homeassistant.components.camera.async_get_image",
            return_value=camera.Image("image/jpeg", b"I play the sax\n"),
        ) as mock_get_image,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MESSAGE: "Hello",
                ATTR_TITLE: "World",
                ATTR_IMAGE: {
                    "media_content_id": "media-source://camera/camera.demo_camera",
                    "media_content_type": "image/jpeg",
                },
            },
            blocking=True,
        )
    mock_get_image.assert_called_once_with(hass, "camera.demo_camera")
    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World", image_file=b"I play the sax\n"
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


@pytest.mark.freeze_time("1970-01-01T00:00:00+00:00")
async def test_nfandroidtv_send_message_image_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message with image snapshot via nfandroidtv.send_message action."""
    entity_id = "notify.android_tv_fire_tv_1_2_3_4"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    with patch(
        "homeassistant.components.image.async_get_image",
        return_value=image.Image(content_type="image/png", content=b"\x89PNG"),
    ) as mock_get_image:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MESSAGE: "Hello",
                ATTR_TITLE: "World",
                ATTR_ICON: {
                    "media_content_id": "media-source://image/image.test",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )
    mock_get_image.assert_called_once_with(hass, "image.test")
    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World", icon=b"\x89PNG"
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


@pytest.mark.freeze_time("1970-01-01T00:00:00+00:00")
async def test_nfandroidtv_send_message_local_media_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message with local media source via nfandroidtv.send_message action."""
    assert await async_setup_component(hass, "media_source", {})
    entity_id = "notify.android_tv_fire_tv_1_2_3_4"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    with (
        patch("pathlib.Path.read_bytes", return_value=b"\x89PNG"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MESSAGE: "Hello",
                ATTR_TITLE: "World",
                ATTR_ICON: {
                    "media_content_id": "media-source://media_source/local/screenshot.png",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )
    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World", icon=b"\x89PNG"
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


@pytest.mark.freeze_time("1970-01-01T00:00:00+00:00")
async def test_nfandroidtv_send_message_unsupported_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message with unsupported media source via nfandroidtv.send_message action."""
    assert await async_setup_component(hass, "media_source", {})
    entity_id = "notify.android_tv_fire_tv_1_2_3_4"
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    with (
        patch(
            "homeassistant.components.nfandroidtv.notify.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="https://example.com/screenshot.png",
                mime_type="image/png",
                path=None,
            ),
        ),
        pytest.raises(ServiceValidationError) as err,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MESSAGE: "Hello",
                ATTR_TITLE: "World",
                ATTR_IMAGE: {
                    "media_content_id": "media-source://media_source/local/screenshot.png",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )
    assert err.value.translation_key == "media_source_not_supported"


async def test_nfandroidtv_send_message_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_notifications_android_tv: AsyncMock,
) -> None:
    """Test sending a message via nfandroidtv.send_message action with exception."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_notifications_android_tv.send.side_effect = ConnectError

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.android_tv_fire_tv_1_2_3_4",
                ATTR_MESSAGE: "Hello",
                ATTR_TITLE: "World",
            },
            blocking=True,
        )

    assert err.value.translation_key == "notify_connection_error"
    assert err.value.translation_placeholders == {CONF_NAME: NAME}

    mock_notifications_android_tv.send.assert_called_once_with(
        message="Hello", title="World"
    )
