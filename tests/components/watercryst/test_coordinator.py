"""Tests for WATERCryst update coordinators."""

from asyncio import CancelledError
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pyocat import WTCApiDisabledError, WTCApiTemporaryError, WTCApiUnauthorizedError
import pytest

from homeassistant.components.watercryst.coordinator import (
    WatercrystMeasurementsUpdateCoordinator,
    WatercrystStateUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import (
    DEFAULT_MEASUREMENT_RESPONSE,
    DEFAULT_STATE_RESPONSE,
    OFFLINE_STATE_RESPONSE,
    http_status_error,
    request_error,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("language", "expected_locale"),
    [("de-AT", "de"), ("fr-FR", "en")],
)
async def test_state_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    language: str,
    expected_locale: str,
) -> None:
    """Test successful state update."""
    hass.config.language = language

    coordinator = WatercrystStateUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_api_client,
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data is DEFAULT_STATE_RESPONSE
    mock_api_client.get_state.assert_awaited_once_with(locale=expected_locale)


async def test_measurements_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test successful measurements update."""
    state = MagicMock(spec=WatercrystStateUpdateCoordinator)
    state.data = DEFAULT_STATE_RESPONSE

    coordinator = WatercrystMeasurementsUpdateCoordinator(
        hass=hass, config_entry=config_entry, client=mock_api_client, state=state
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data is DEFAULT_MEASUREMENT_RESPONSE
    mock_api_client.get_measurements.assert_awaited_once()


@pytest.mark.parametrize(
    "response",
    [None, OFFLINE_STATE_RESPONSE],
)
async def test_measurements_update_failed_device_offline(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    response: Any,
) -> None:
    """Test failed measurements update because the device is offline."""
    state = MagicMock(spec=WatercrystStateUpdateCoordinator)
    state.data = response

    coordinator = WatercrystMeasurementsUpdateCoordinator(
        hass=hass, config_entry=config_entry, client=mock_api_client, state=state
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    mock_api_client.get_measurements.assert_not_awaited()


@pytest.mark.parametrize(
    "exception",
    [
        WTCApiDisabledError(),
        WTCApiTemporaryError(),
        request_error(),
        http_status_error(503),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test failed state update because of an exception."""
    mock_api_client.get_state.side_effect = exception

    coordinator = WatercrystStateUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_api_client,
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_update_failed_unauthorized(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test failed state update because of a missing authorization."""
    mock_api_client.get_state.side_effect = WTCApiUnauthorizedError()

    coordinator = WatercrystStateUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_api_client,
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_update_failed_cancelled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test failed state update because it was cancelled."""
    mock_api_client.get_state.side_effect = CancelledError()

    coordinator = WatercrystStateUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_api_client,
    )

    with pytest.raises(CancelledError):
        await coordinator._async_update_data()
