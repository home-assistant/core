"""Test the Reolink services."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from reolink_aio.api import Chime
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.reolink.const import DOMAIN
from homeassistant.components.reolink.services import (
    ATTR_RINGTONE,
    ATTR_TIMESTAMP,
    SERVICE_SNAPSHOT_PAST,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_FILENAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import TEST_CAM_NAME

from tests.common import MockConfigEntry

TEST_FILE = "/test/snapshot.jpg"
TEST_CAMERA_ID = f"{Platform.CAMERA}.{TEST_CAM_NAME}_fluent"


async def test_play_chime_service_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    reolink_chime: Chime,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test chime play service."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.test_chime_visitor_ringtone"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    device_id = entity.device_id

    # Test chime play service with device
    reolink_chime.play = AsyncMock()
    await hass.services.async_call(
        DOMAIN,
        "play_chime",
        {ATTR_DEVICE_ID: [device_id], ATTR_RINGTONE: "attraction"},
        blocking=True,
    )
    reolink_chime.play.assert_called_once()

    # Test errors
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "play_chime",
            {ATTR_DEVICE_ID: ["invalid_id"], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )

    reolink_chime.play = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "play_chime",
            {ATTR_DEVICE_ID: [device_id], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )

    reolink_chime.play = AsyncMock(side_effect=InvalidParameterError("Test error"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "play_chime",
            {ATTR_DEVICE_ID: [device_id], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )

    reolink_host.chime.return_value = None
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "play_chime",
            {ATTR_DEVICE_ID: [device_id], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )


async def test_play_chime_service_unloaded(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    reolink_chime: Chime,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test chime play service when config entry is unloaded."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.test_chime_visitor_ringtone"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    device_id = entity.device_id

    # Unload the config entry
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    # Test chime play service
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "play_chime",
            {ATTR_DEVICE_ID: [device_id], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )


@pytest.fixture
async def camera_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> MockConfigEntry:
    """Set up the Reolink camera platform."""
    # the camera is in UTC while Home Assistant is in US/Pacific
    reolink_host.timezone.return_value = dt_util.UTC

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, config_entry)
    return config_entry


@pytest.mark.usefixtures("camera_config_entry")
async def test_snapshot_past_service(
    hass: HomeAssistant,
    reolink_host: MagicMock,
) -> None:
    """Test the snapshot_past service writes the image of the camera to a file."""
    reolink_host.baichuan.snapshot_past = AsyncMock(return_value=b"image")
    mopen = mock_open()

    with (
        patch("homeassistant.components.reolink.services.open", mopen, create=True),
        patch("homeassistant.components.reolink.services.os.makedirs"),
        patch.object(hass.config, "is_allowed_path", return_value=True),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SNAPSHOT_PAST,
            {
                ATTR_ENTITY_ID: TEST_CAMERA_ID,
                ATTR_TIMESTAMP: "2025-09-29 14:30:00",
                CONF_FILENAME: TEST_FILE,
            },
            blocking=True,
        )

    # a naive timestamp is interpreted in the Home Assistant timezone (US/Pacific)
    # and converted to the timezone of the camera (UTC)
    reolink_host.baichuan.snapshot_past.assert_called_once_with(
        0, datetime(2025, 9, 29, 21, 30, tzinfo=dt_util.UTC), "sub", "ffmpeg"
    )
    mopen.assert_called_once_with(TEST_FILE, "wb")
    assert mopen().write.mock_calls[0][1][0] == b"image"


@pytest.mark.usefixtures("camera_config_entry")
async def test_snapshot_past_service_not_allowed_path(
    hass: HomeAssistant,
    reolink_host: MagicMock,
) -> None:
    """Test the snapshot_past service with a path that is not allowed."""
    reolink_host.baichuan.snapshot_past = AsyncMock(return_value=b"image")

    with (
        patch.object(hass.config, "is_allowed_path", return_value=False),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SNAPSHOT_PAST,
            {
                ATTR_ENTITY_ID: TEST_CAMERA_ID,
                ATTR_TIMESTAMP: "2025-09-29 14:30:00",
                CONF_FILENAME: TEST_FILE,
            },
            blocking=True,
        )

    reolink_host.baichuan.snapshot_past.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (ReolinkError("Test error"), HomeAssistantError),
        (InvalidParameterError("Test error"), ServiceValidationError),
    ],
    ids=["reolink_error", "invalid_parameter"],
)
@pytest.mark.usefixtures("camera_config_entry")
async def test_snapshot_past_service_errors(
    hass: HomeAssistant,
    reolink_host: MagicMock,
    side_effect: Exception,
    expected: type[Exception],
) -> None:
    """Test the snapshot_past service when the camera returns an error."""
    reolink_host.baichuan.snapshot_past = AsyncMock(side_effect=side_effect)

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(expected),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SNAPSHOT_PAST,
            {
                ATTR_ENTITY_ID: TEST_CAMERA_ID,
                ATTR_TIMESTAMP: "2025-09-29 14:30:00",
                CONF_FILENAME: TEST_FILE,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("camera_config_entry")
async def test_snapshot_past_service_write_error(
    hass: HomeAssistant,
    reolink_host: MagicMock,
) -> None:
    """Test the snapshot_past service when the image can not be written to disk."""
    reolink_host.baichuan.snapshot_past = AsyncMock(return_value=b"image")

    with (
        patch(
            "homeassistant.components.reolink.services.open",
            side_effect=OSError("Test error"),
            create=True,
        ),
        patch("homeassistant.components.reolink.services.os.makedirs"),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SNAPSHOT_PAST,
            {
                ATTR_ENTITY_ID: TEST_CAMERA_ID,
                ATTR_TIMESTAMP: "2025-09-29 14:30:00",
                CONF_FILENAME: TEST_FILE,
            },
            blocking=True,
        )
