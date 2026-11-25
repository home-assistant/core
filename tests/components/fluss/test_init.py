"""Test script for Fluss+ integration initialization."""

import logging
from typing import Any
from unittest.mock import AsyncMock

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
    FlussDeviceOfflineError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.fluss.const import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test the Fluss configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_api_client.async_get_devices.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (FlussApiClientAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (FlussApiClientCommunicationError, ConfigEntryState.SETUP_RETRY),
        (FlussApiClientError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_async_setup_entry_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test that an authentication error during setup leads to SETUP_ERROR state."""
    mock_api_client.async_get_devices.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_offline_device_stays_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """A 503 keeps the device but marks it offline; the rest still load."""

    async def _status(device_id: str) -> dict[str, Any]:
        if device_id == "2a303030sdj1":
            raise FlussDeviceOfflineError("offline")
        return {"status": {"internetConnected": True}}

    mock_api_client.async_get_device_status.side_effect = _status
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("button.device_1").state == STATE_UNAVAILABLE
    assert hass.states.get("button.device_2").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "exception",
    [
        FlussApiClientError("boom"),
        FlussApiClientAuthenticationError("permission revoked"),
    ],
)
async def test_failed_status_does_not_fail_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    exception: Exception,
) -> None:
    """A non-offline status error is best-effort: setup still completes."""

    async def _status(device_id: str) -> dict[str, Any]:
        if device_id == "2a303030sdj1":
            raise exception
        return {"status": {"internetConnected": True}}

    mock_api_client.async_get_device_status.side_effect = _status
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # device_1 has no status; it stays usable as a trigger button
    assert hass.states.get("button.device_1").state == STATE_UNKNOWN
    assert hass.states.get("button.device_2").state == STATE_UNKNOWN


async def test_status_error_logged_once_until_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A refused status read is logged once, and its recovery is logged once."""
    caplog.set_level(logging.INFO, logger="homeassistant.components.fluss")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    failed = "Error fetching status for 2a303030sdj1"
    recovered = "Status for 2a303030sdj1 is available again"

    def _logged(message: str) -> list[logging.LogRecord]:
        return [record for record in caplog.records if message in record.message]

    caplog.clear()
    mock_api_client.async_get_device_status.side_effect = FlussApiClientError(
        "API usage limit exceeded"
    )
    for _ in range(2):
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(_logged(failed)) == 1
    assert _logged(failed)[0].levelno == logging.INFO

    mock_api_client.async_get_device_status.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(_logged(recovered)) == 1
    assert _logged(recovered)[0].levelno == logging.INFO

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(_logged(recovered)) == 1
