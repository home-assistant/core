"""Tests for the Paperless-ngx coordinator."""

from datetime import datetime, timedelta

from freezegun import freeze_time
from pypaperless.exceptions import (
    PaperlessConnectionError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
import pytest

from homeassistant.components.paperless_ngx.const import (
    REMOTE_VERSION_UPDATE_INTERVAL_HOURS,
)
from homeassistant.components.paperless_ngx.coordinator import (
    PaperlessCoordinator,
    PaperlessData,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady


@pytest.mark.asyncio
async def test_coordinator_successful_update(
    hass: HomeAssistant,
    mock_config_entry,
    mock_remote_status_data,
) -> None:
    """Test coordinator fetches data successfully."""
    mock_config_entry.add_to_hass(hass)
    coordinator = PaperlessCoordinator(hass, mock_config_entry)

    data = await coordinator._async_update_data()

    assert data.remote_version == await mock_remote_status_data()
    assert isinstance(data, PaperlessData)


@pytest.mark.asyncio
async def test_remote_version_github_rate_limit_response_none(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
) -> None:
    """Test that Remote Version is none if GitHub rate limit is reached."""
    mock_config_entry.add_to_hass(hass)
    mock_client.remote_version.return_value.version = "0.0.0"
    coordinator = PaperlessCoordinator(hass, mock_config_entry)

    data = await coordinator._async_update_data()

    assert data.remote_version is None


@pytest.mark.asyncio
async def test_remote_version_rate_limit_respected(
    hass: HomeAssistant, mock_config_entry, mock_client
) -> None:
    """Test remote version is not fetched again if within the rate limit window."""
    mock_config_entry.add_to_hass(hass)
    coordinator = PaperlessCoordinator(hass, mock_config_entry)
    base_frozen_dt = datetime(2025, 5, 19, 12, 0, 0)

    with freeze_time(base_frozen_dt):
        await coordinator._async_refresh()
        assert mock_client.remote_version.call_count == 1

    frozen_dt = base_frozen_dt + timedelta(minutes=30)
    with freeze_time(frozen_dt):
        await coordinator._async_refresh()
        assert mock_client.remote_version.call_count == 1

    frozen_dt = base_frozen_dt + timedelta(hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS)
    with freeze_time(frozen_dt):
        await coordinator._async_refresh()
        assert mock_client.remote_version.call_count == 2

    frozen_dt = base_frozen_dt + timedelta(
        minutes=30, hours=REMOTE_VERSION_UPDATE_INTERVAL_HOURS
    )
    with freeze_time(frozen_dt):
        await coordinator._async_refresh()
        assert mock_client.remote_version.call_count == 2


@pytest.mark.asyncio
async def test_connection_error_raises_not_ready(
    hass: HomeAssistant, mock_config_entry, mock_client
) -> None:
    """Test invalid token error raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)
    mock_client.remote_version.side_effect = PaperlessConnectionError()

    coordinator = PaperlessCoordinator(hass, mock_config_entry)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_invalid_token_raises_entry_error(
    hass: HomeAssistant, mock_config_entry, mock_client
) -> None:
    """Test invalid token error raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)
    mock_client.remote_version.side_effect = PaperlessInvalidTokenError()

    coordinator = PaperlessCoordinator(hass, mock_config_entry)

    with pytest.raises(ConfigEntryError):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_inactive_or_deleted_user_raises_entry_error(
    hass: HomeAssistant, mock_config_entry, mock_client
) -> None:
    """Test inactive or deleted user raises ConfigEntryError."""
    mock_config_entry.add_to_hass(hass)
    mock_client.remote_version.side_effect = PaperlessInactiveOrDeletedError()

    coordinator = PaperlessCoordinator(hass, mock_config_entry)

    with pytest.raises(ConfigEntryError):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_github_rate_limit_logged_only_once(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that GitHub rate limit warning is logged only once."""

    mock_config_entry.add_to_hass(hass)

    mock_client.remote_version.return_value.version = "0.0.0"

    coordinator = PaperlessCoordinator(hass, mock_config_entry)

    with caplog.at_level("WARNING"):
        await coordinator._get_paperless_remote_version()

    assert "GitHub rate limit of 60 requests per hour is reached" in caplog.text

    caplog.clear()

    with caplog.at_level("WARNING"):
        await coordinator._get_paperless_remote_version()

    assert "GitHub rate limit of 60 requests per hour is reached" not in caplog.text
