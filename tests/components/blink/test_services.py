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
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry

CAMERA_NAME = "Camera 1"
FILENAME = "blah"
PIN = "1234"


async def test_refresh_service_calls(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refrest service calls."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_blink_api.refresh.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH,
        {ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id]},
        blocking=True,
    )

    assert mock_blink_api.refresh.call_count == 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            {ATTR_CONFIG_ENTRY_ID: ["bad-config_id"]},
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


@pytest.mark.parametrize(
    ("service", "params"),
    [
        (SERVICE_SEND_PIN, {CONF_PIN: PIN}),
        (SERVICE_REFRESH, {}),
    ],
)
async def test_service_called_with_non_blink_device(
    hass: HomeAssistant,
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
    other_mock_config_entry = MockConfigEntry(
        title="Not Blink", domain=other_domain, entry_id=other_config_id
    )
    await hass.config_entries.async_add(other_mock_config_entry)

    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    parameters = {ATTR_CONFIG_ENTRY_ID: [other_mock_config_entry.entry_id]}
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
        (SERVICE_REFRESH, {}),
    ],
)
async def test_service_called_with_unloaded_entry(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    service,
    params,
) -> None:
    """Test service calls with not ready config entry."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_config_entry.state = ConfigEntryState.SETUP_ERROR
    hass.config.is_allowed_path = Mock(return_value=True)
    mock_blink_api.cameras = {CAMERA_NAME: AsyncMock()}

    parameters = {ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id]}
    parameters.update(params)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            service,
            parameters,
            blocking=True,
        )
