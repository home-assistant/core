"""Tests for WATERCryst update coordinators."""

from asyncio import CancelledError
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyocat import WTCApiDisabledError, WTCApiTemporaryError, WTCApiUnauthorizedError
import pytest

from homeassistant.components.watercryst.coordinator import (
    StateResponse,
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

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("language", "expected_locale"),
    [("de-AT", "de"), ("fr-FR", "en")],
)
async def test_state_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    language: str,
    expected_locale: str,
) -> None:
    """Test successful state update."""
    hass.config.language = language

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.runtime_data.state.last_update_success
    assert config_entry.runtime_data.state.data is DEFAULT_STATE_RESPONSE
    mock_api_client.get_state.assert_awaited_with(locale=expected_locale)


async def test_measurements_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful measurements update."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.runtime_data.measurements.last_update_success
    assert config_entry.runtime_data.measurements.data is DEFAULT_MEASUREMENT_RESPONSE
    mock_api_client.get_measurements.assert_awaited()


@pytest.mark.parametrize(
    "response",
    [None, OFFLINE_STATE_RESPONSE],
)
async def test_measurements_update_failed_device_offline(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    response: StateResponse | None,
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
