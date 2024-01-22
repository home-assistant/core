"""Test the Blink services."""
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from homeassistant.components.blink.const import (
    DOMAIN,
    SERVICE_REFRESH,
    SERVICE_SAVE_RECENT_CLIPS,
    SERVICE_SAVE_VIDEO,
    SERVICE_SEND_PIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_FILE_PATH,
    CONF_FILENAME,
    CONF_NAME,
    CONF_PIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

CAMERA_NAME = "Camera 1"
FILENAME = "blah"
PIN = "1234"


async def test_refresh_service_calls(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refrest service calls."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})

    assert device_entry

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_blink_api.refresh.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH,
        {ATTR_DEVICE_ID: [device_entry.id]},
        blocking=True,
    )

    assert mock_blink_api.refresh.call_count == 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            {ATTR_DEVICE_ID: ["bad-device_id"]},
            blocking=True,
        )


async def test_video_service_calls(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test video service calls."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})

    assert device_entry

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_blink_api.refresh.call_count == 1

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_VIDEO,
            {
                ATTR_DEVICE_ID: [device_entry.id],
                CONF_NAME: CAMERA_NAME,
                CONF_FILENAME: FILENAME,
            },
            blocking=True,
        )

    hass.config.is_allowed_path = Mock(return_value=True)
    caplog.clear()
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SAVE_VIDEO,
        {
            ATTR_DEVICE_ID: [device_entry.id],
            CONF_NAME: CAMERA_NAME,
            CONF_FILENAME: FILENAME,
        },
        blocking=True,
    )
    mock_blink_api.cameras[CAMERA_NAME].video_to_file.assert_awaited_once()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_VIDEO,
            {
                ATTR_DEVICE_ID: ["bad-device_id"],
                CONF_NAME: CAMERA_NAME,
                CONF_FILENAME: FILENAME,
            },
            blocking=True,
        )

    mock_blink_api.cameras[CAMERA_NAME].video_to_file = AsyncMock(side_effect=OSError)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_VIDEO,
            {
                ATTR_DEVICE_ID: [device_entry.id],
                CONF_NAME: CAMERA_NAME,
                CONF_FILENAME: FILENAME,
            },
            blocking=True,
        )

    hass.config.is_allowed_path = Mock(return_value=False)


async def test_picture_service_calls(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test picture servcie calls."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})

    assert device_entry

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_blink_api.refresh.call_count == 1

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_RECENT_CLIPS,
            {
                ATTR_DEVICE_ID: [device_entry.id],
                CONF_NAME: CAMERA_NAME,
                CONF_FILE_PATH: FILENAME,
            },
            blocking=True,
        )

    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SAVE_RECENT_CLIPS,
        {
            ATTR_DEVICE_ID: [device_entry.id],
            CONF_NAME: CAMERA_NAME,
            CONF_FILE_PATH: FILENAME,
        },
        blocking=True,
    )
    mock_blink_api.cameras[CAMERA_NAME].save_recent_clips.assert_awaited_once()

    mock_blink_api.cameras[CAMERA_NAME].save_recent_clips = AsyncMock(
        side_effect=OSError
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_RECENT_CLIPS,
            {
                ATTR_DEVICE_ID: [device_entry.id],
                CONF_NAME: CAMERA_NAME,
                CONF_FILE_PATH: FILENAME,
            },
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_RECENT_CLIPS,
            {
                ATTR_DEVICE_ID: ["bad-device_id"],
                CONF_NAME: CAMERA_NAME,
                CONF_FILE_PATH: FILENAME,
            },
            blocking=True,
        )


async def test_pin_service_calls(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pin service calls."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})

    assert device_entry

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_blink_api.refresh.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_PIN,
        {ATTR_DEVICE_ID: [device_entry.id], CONF_PIN: PIN},
        blocking=True,
    )
    assert mock_blink_api.auth.send_auth_key.assert_awaited_once

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            {ATTR_DEVICE_ID: ["bad-device_id"], CONF_PIN: PIN},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "params"),
    [
        (SERVICE_SEND_PIN, {CONF_PIN: PIN}),
        (
            SERVICE_SAVE_RECENT_CLIPS,
            {
                CONF_NAME: CAMERA_NAME,
                CONF_FILE_PATH: FILENAME,
            },
        ),
        (
            SERVICE_SAVE_VIDEO,
            {
                CONF_NAME: CAMERA_NAME,
                CONF_FILENAME: FILENAME,
            },
        ),
    ],
)
async def test_service_called_with_non_blink_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    service,
    params,
) -> None:
    """Test service calls with non blink device."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    other_domain = "NotBlink"
    other_config_id = "555"
    await hass.config_entries.async_add(
        MockConfigEntry(
            title="Not Blink", domain=other_domain, entry_id=other_config_id
        )
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_id,
        identifiers={
            (other_domain, 1),
        },
    )

    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    parameters = {ATTR_DEVICE_ID: [device_entry.id]}
    parameters.update(params)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            service,
            parameters,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "params"),
    [
        (SERVICE_SEND_PIN, {CONF_PIN: PIN}),
        (
            SERVICE_SAVE_RECENT_CLIPS,
            {
                CONF_NAME: CAMERA_NAME,
                CONF_FILE_PATH: FILENAME,
            },
        ),
        (
            SERVICE_SAVE_VIDEO,
            {
                CONF_NAME: CAMERA_NAME,
                CONF_FILENAME: FILENAME,
            },
        ),
    ],
)
async def test_service_called_with_unloaded_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    service,
    params,
) -> None:
    """Test service calls with unloaded config entry."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.async_unload(hass)

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})

    assert device_entry

    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    parameters = {ATTR_DEVICE_ID: [device_entry.id]}
    parameters.update(params)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            service,
            parameters,
            blocking=True,
        )
