"""Test the DVLA integration setup."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from aio_dvla_vehicle_enquiry import (
    DVLAAuthError,
    DVLAError,
    DVLAInvalidRegistrationError,
    DVLARateLimitError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.dvla.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry(
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
    mock_dvla_client: AsyncMock,
) -> None:
    """Test setting up a config entry."""
    entry = await setup_dvla_entry()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.reg_number == "AB12CDE"
    mock_dvla_client.assert_awaited_once_with("AB12CDE")


async def test_unload_entry(
    hass: HomeAssistant,
    setup_dvla_entry: Callable[
        [dict[str, Any] | None],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test unloading a config entry."""
    entry = await setup_dvla_entry()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_retries_on_dvla_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test setup retries when DVLA update fails."""
    mock_config_entry.add_to_hass(hass)
    mock_dvla_client.side_effect = DVLAError("DVLA unavailable")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    assert mock_config_entry.error_reason_translation_key == "update_failed"


@pytest.mark.parametrize(
    ("error", "translation_key", "placeholders"),
    [
        pytest.param(
            DVLAAuthError("Raw DVLA response"), "auth_failed", None, id="auth"
        ),
        pytest.param(
            DVLAInvalidRegistrationError("Raw DVLA response"),
            "vehicle_not_found",
            {"reg_number": "AB12CDE"},
            id="registration",
        ),
    ],
)
async def test_setup_entry_fails_without_retry_or_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dvla_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error: DVLAError,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test a rejected key or registration stops setup with a translated error."""
    mock_config_entry.add_to_hass(hass)
    mock_dvla_client.side_effect = error

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders == placeholders
    assert not hass.config_entries.flow.async_progress()
    assert "Raw DVLA response" not in caplog.text

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_dvla_client.assert_awaited_once_with("AB12CDE")


async def test_setup_entry_rate_limit_waits_before_retrying(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dvla_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup does not immediately retry a rate-limited shared key."""
    mock_config_entry.add_to_hass(hass)
    mock_dvla_client.side_effect = DVLARateLimitError("Too many requests")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "rate_limited"

    mock_dvla_client.side_effect = None
    freezer.tick(timedelta(minutes=59))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_dvla_client.assert_awaited_once_with("AB12CDE")

    freezer.tick(timedelta(minutes=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_dvla_client.await_count == 2
