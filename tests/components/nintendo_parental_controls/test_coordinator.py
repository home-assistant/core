"""Test coordinator error handling."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pynintendoauth.exceptions import (
    HttpException,
    InvalidOAuthConfigurationException,
    InvalidSessionTokenException,
)
from pynintendoparental.exceptions import NoDevicesFoundException
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.parametrize(
    ("exception", "translation_key", "expected_state", "expected_log_message"),
    [
        (
            InvalidOAuthConfigurationException(
                status_code=401, message="Authentication failed"
            ),
            "invalid_auth",
            ConfigEntryState.SETUP_ERROR,
            None,
        ),
        (
            NoDevicesFoundException(),
            "no_devices_found",
            ConfigEntryState.SETUP_ERROR,
            None,
        ),
        (
            HttpException(
                status_code=400, error_code="update_required", message="Update required"
            ),
            "update_required",
            ConfigEntryState.SETUP_ERROR,
            None,
        ),
        (
            HttpException(
                status_code=500, error_code="unknown", message="Unknown error"
            ),
            None,
            ConfigEntryState.SETUP_RETRY,
            None,
        ),
        (
            InvalidSessionTokenException(
                status_code=403, error_code="invalid_token", message="Invalid token"
            ),
            None,
            ConfigEntryState.SETUP_RETRY,
            "Session token invalid, will renew on next update",
        ),
    ],
)
async def test_update_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
    translation_key: str,
    expected_state: ConfigEntryState,
    expected_log_message: str | None,
) -> None:
    """Test handling of update errors."""
    mock_nintendo_client.discover_devices.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    # Ensure no entities are created
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 0

    # Ensure the config entry is marked as expected state
    assert mock_config_entry.state is expected_state

    # Ensure the correct translation key is used in the error
    assert mock_config_entry.error_reason_translation_key == translation_key

    # If there's an expected log message, check that it was logged
    if expected_log_message:
        assert expected_log_message in caplog.text


@pytest.mark.parametrize(
    "exception",
    [
        HttpException(status_code=500, error_code="unknown", message="Unknown error"),
        TimeoutError(),
        ClientError(),
    ],
)
async def test_device_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
) -> None:
    """Test entities are unavailable when their device fails to update."""
    await setup_integration(hass, mock_config_entry)
    entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ]
    assert entity_ids
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    mock_nintendo_device.update.side_effect = exception
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert mock_config_entry.runtime_data.last_update_success
    assert (
        "Updating Nintendo device Home Assistant Test failed, marking it unavailable"
        in caplog.text
    )

    mock_nintendo_device.update.side_effect = None
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
    assert "Nintendo device Home Assistant Test is available again" in caplog.text


async def test_device_update_failure_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities start unavailable when their device fails to update on setup."""
    mock_nintendo_device.update.side_effect = HttpException(
        status_code=500, error_code="unknown", message="Unknown error"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ]
    assert entity_ids
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_device_update_invalid_session_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a token rejected while updating a device fails the whole update."""
    await setup_integration(hass, mock_config_entry)

    mock_nintendo_device.update.side_effect = InvalidSessionTokenException(
        status_code=401, message="invalid_token"
    )
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_config_entry.runtime_data.last_update_success
    assert "Session token invalid, will renew on next update" in caplog.text
