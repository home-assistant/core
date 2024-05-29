"""Test the Blink services."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from homeassistant.components.blink.const import (
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    SERVICE_REFRESH,
    SERVICE_SEND_PIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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


async def test_pin_service_calls(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pin service calls."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_blink_api.refresh.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_PIN,
        {ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id], CONF_PIN: PIN},
        blocking=True,
    )
    assert mock_blink_api.auth.send_auth_key.assert_awaited_once

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            {ATTR_CONFIG_ENTRY_ID: ["bad-config_id"], CONF_PIN: PIN},
            blocking=True,
        )


async def test_service_pin_called_with_non_blink_device(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pin service calls with non blink device."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    other_domain = "NotBlink"
    other_config_id = "555"
    other_mock_config_entry = MockConfigEntry(
        title="Not Blink", domain=other_domain, entry_id=other_config_id
    )
    other_mock_config_entry.add_to_hass(hass)

    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    parameters = {
        ATTR_CONFIG_ENTRY_ID: [other_mock_config_entry.entry_id],
        CONF_PIN: PIN,
    }

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            parameters,
            blocking=True,
        )


async def test_service_update_called_with_non_blink_device(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test update service calls with non blink device."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    other_domain = "NotBlink"
    other_config_id = "555"
    other_mock_config_entry = MockConfigEntry(
        title="Not Blink", domain=other_domain, entry_id=other_config_id
    )
    other_mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_id,
        identifiers={
            (other_domain, 1),
        },
    )

    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    parameters = {ATTR_DEVICE_ID: [device_entry.id]}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            parameters,
            blocking=True,
        )


async def test_service_pin_called_with_unloaded_entry(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pin service calls with not ready config entry."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_config_entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)
    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    parameters = {ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id], CONF_PIN: PIN}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            parameters,
            blocking=True,
        )


async def test_service_update_called_with_unloaded_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test update service calls with not ready config entry."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_config_entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)
    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "12345")})
    assert device_entry

    parameters = {ATTR_DEVICE_ID: [device_entry.id]}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            parameters,
            blocking=True,
        )
