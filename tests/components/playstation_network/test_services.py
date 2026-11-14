"""Tests for the PlayStation Network actions."""

import errno
from typing import Any
from unittest.mock import MagicMock, patch

from psnawp_api.core.psnawp_exceptions import (
    PSNAWPClientError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import media_source
from homeassistant.components.playstation_network.const import DOMAIN
from homeassistant.components.playstation_network.services import (
    PlayStationNetworkService,
    PlayStationNetworkServiceArgument,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, CommonServiceArgument
from homeassistant.core import HomeAssistant, HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    ("image", "payload"),
    [
        pytest.param(
            {
                "media_content_id": "media-source://camera/camera.demo_camera",
                "media_content_type": "image/jpeg",
            },
            b"\xff\xd8\xff\xdb\n",
            id="camera",
        ),
        pytest.param(
            {
                "media_content_id": "media-source://image/image.test",
                "media_content_type": "image/png",
            },
            b"\x89PNG\n",
            id="image",
        ),
    ],
)
@pytest.mark.parametrize(
    "entity_id",
    [
        "notify.testuser_group_publicuniversalfriend",
        "notify.testuser_direct_message_publicuniversalfriend",
    ],
)
@pytest.mark.freeze_time("2025-07-28T00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_image(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    entity_id: str,
    image: dict[str, Any],
    payload: bytes,
) -> None:
    """Test send image with camera and image sources."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    with (
        patch(
            "homeassistant.components.playstation_network.helpers.async_get_media_image",
            return_value=media_source.MediaImage(payload, "image/jpeg"),
        ) as mock_get_image,
    ):
        await hass.services.async_call(
            DOMAIN,
            PlayStationNetworkService.SEND_IMAGE,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                PlayStationNetworkServiceArgument.IMAGE: image,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2025-07-28T00:00:00+00:00"
    mock_psnawpapi.group.return_value.send_image.assert_called_once_with(payload)

    mock_get_image.assert_called_once_with(hass, image["media_content_id"])


@pytest.mark.parametrize(
    "entity_id",
    [
        "notify.testuser_group_publicuniversalfriend",
        "notify.testuser_direct_message_publicuniversalfriend",
    ],
)
@pytest.mark.freeze_time("2025-07-28T00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_image_local_media_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    entity_id: str,
) -> None:
    """Test send image with local media source."""
    assert await async_setup_component(hass, "media_source", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        PlayStationNetworkService.SEND_IMAGE,
        {
            CommonServiceArgument.ENTITY_ID: entity_id,
            PlayStationNetworkServiceArgument.IMAGE: {
                "media_content_id": (
                    "media-source://media_source/local/screenshot.jpg"
                ),
                "media_content_type": "image/jpeg",
            },
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2025-07-28T00:00:00+00:00"
    mock_psnawpapi.group.return_value.send_image.assert_called_once_with(
        b"\xff\xd8\xff\xdb\n"
    )


@pytest.mark.freeze_time("2025-07-28T00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_image_media_source_not_supported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test send image media source not supported errors."""
    entity_id = "notify.testuser_group_publicuniversalfriend"
    assert await async_setup_component(hass, "media_source", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    with (
        patch(
            "homeassistant.components.playstation_network.helpers.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="https://gameclipscontent-d2009.media.xboxlive.com/123456789",
                mime_type="audio/mpeg",
                path=None,
            ),
        ),
        pytest.raises(ServiceValidationError) as exc,
    ):
        await hass.services.async_call(
            DOMAIN,
            PlayStationNetworkService.SEND_IMAGE,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                PlayStationNetworkServiceArgument.IMAGE: {
                    "media_content_id": "media-source://xbox/123456789/",
                    "media_content_type": "video/mp4",
                },
            },
            blocking=True,
        )
    assert exc.value.translation_key == "media_source_not_supported"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    mock_psnawpapi.group.return_value.send_image.assert_not_called()


@pytest.mark.freeze_time("2025-07-28T00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_image_unsupported_media_type(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test send image unsupported media type errors."""
    entity_id = "notify.testuser_group_publicuniversalfriend"
    assert await async_setup_component(hass, "media_source", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    with (
        pytest.raises(ServiceValidationError) as exc,
    ):
        await hass.services.async_call(
            DOMAIN,
            PlayStationNetworkService.SEND_IMAGE,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                PlayStationNetworkServiceArgument.IMAGE: {
                    "media_content_id": (
                        "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4"
                    ),
                    "media_content_type": "video/mp4",
                },
            },
            blocking=True,
        )
    assert exc.value.translation_key == "unsupported_media_type"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    mock_psnawpapi.group.return_value.send_image.assert_not_called()


@pytest.mark.freeze_time("2025-07-28T00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_image_max_file_size_exceeded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test send image max file size exceeded errors."""
    entity_id = "notify.testuser_group_publicuniversalfriend"
    assert await async_setup_component(hass, "media_source", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    with (
        patch("homeassistant.components.playstation_network.helpers.MAX_IMAGE_SIZE", 1),
        pytest.raises(ServiceValidationError) as exc,
    ):
        await hass.services.async_call(
            DOMAIN,
            PlayStationNetworkService.SEND_IMAGE,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                PlayStationNetworkServiceArgument.IMAGE: {
                    "media_content_id": (
                        "media-source://media_source/local/screenshot.jpg"
                    ),
                    "media_content_type": "image/jpeg",
                },
            },
            blocking=True,
        )
    assert exc.value.translation_key == "max_file_size_exceeded"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    mock_psnawpapi.group.return_value.send_image.assert_not_called()


@pytest.mark.freeze_time("2025-07-28T00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_send_image_file_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test send image file not found errors."""
    entity_id = "notify.testuser_group_publicuniversalfriend"
    assert await async_setup_component(hass, "media_source", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    with (
        patch(
            "pathlib.Path.read_bytes",
            side_effect=FileNotFoundError(
                errno.ENOENT, "No such file or directory", "/media/screenshot.jpg"
            ),
        ),
        pytest.raises(ServiceValidationError) as exc,
    ):
        await hass.services.async_call(
            DOMAIN,
            PlayStationNetworkService.SEND_IMAGE,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                PlayStationNetworkServiceArgument.IMAGE: {
                    "media_content_id": (
                        "media-source://media_source/local/screenshot.jpg"
                    ),
                    "media_content_type": "image/jpeg",
                },
            },
            blocking=True,
        )
    assert exc.value.translation_key == "os_read_not_found"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    mock_psnawpapi.group.return_value.send_image.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (PSNAWPClientError("error msg"), "send_message_failed"),
        (PSNAWPForbiddenError("error msg"), "send_message_forbidden"),
        (PSNAWPNotFoundError("error msg"), "group_invalid"),
        (PSNAWPServerError("error msg"), "send_message_failed"),
    ],
)
async def test_send_image_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test send image exceptions."""
    assert await async_setup_component(hass, "media_source", {})
    mock_psnawpapi.group.return_value.send_image.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("notify.testuser_group_publicuniversalfriend")
    assert state
    assert state.state == STATE_UNKNOWN

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN,
            PlayStationNetworkService.SEND_IMAGE,
            {
                CommonServiceArgument.ENTITY_ID: "notify.testuser_group_publicuniversalfriend",
                PlayStationNetworkServiceArgument.IMAGE: {
                    "media_content_id": (
                        "media-source://media_source/local/screenshot.jpg"
                    ),
                    "media_content_type": "image/jpeg",
                },
            },
            blocking=True,
        )

    assert exc.value.translation_key == translation_key
    mock_psnawpapi.group.return_value.send_image.assert_called_once_with(
        b"\xff\xd8\xff\xdb\n"
    )
