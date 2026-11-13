"""Tests for WATERCryst update coordinators."""

from asyncio import CancelledError
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyocat import WTCApiDisabledError, WTCApiTemporaryError, WTCApiUnauthorizedError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.components.watercryst.coordinator import (
    DEVICE_INFO_POLLING_INTERVAL,
    MEASUREMENTS_POLLING_INTERVAL,
    STATE_POLLING_INTERVAL,
    WatercrystStateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import (
    ALT_DEVICE_NAME,
    ALT_DEVICE_TYPE_NUMBER,
    ALT_DEVICE_TYPE_SERIES,
    ALT_FW_VERSION,
    ALT_HW_VERSION,
    DEVICE_NAME,
    DEVICE_TYPE_LINE,
    DEVICE_TYPE_NUMBER,
    DEVICE_TYPE_SERIES,
    FW_VERSION,
    HW_VERSION,
    alternative_info_response,
    alternative_measurement_response,
    alternative_state_response,
    default_info_response,
    default_measurement_response,
    default_state_response,
    http_status_error,
    request_error,
)


@pytest.mark.parametrize(
    ("language", "expected_locale"),
    [("de-AT", "de"), ("fr-FR", "en")],
)
async def test_state_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    language: str,
    expected_locale: str,
) -> None:
    """Test successful state update."""
    hass.config.language = language

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(STATE_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.state.last_update_success
    assert mock_config_entry.runtime_data.state.data == default_state_response()
    mock_api_client.get_state.assert_awaited_with(locale=expected_locale)

    mock_api_client.get_state.return_value = None

    freezer.tick(STATE_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.state.last_update_success
    assert mock_config_entry.runtime_data.state.data is None
    mock_api_client.get_state.assert_awaited_with(locale=expected_locale)

    mock_api_client.get_state.return_value = alternative_state_response()

    freezer.tick(STATE_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.state.last_update_success
    assert mock_config_entry.runtime_data.state.data == alternative_state_response()
    mock_api_client.get_state.assert_awaited_with(locale=expected_locale)


async def test_measurements_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful measurements update."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.measurements.last_update_success
    assert (
        mock_config_entry.runtime_data.measurements.data
        == default_measurement_response()
    )
    mock_api_client.get_measurements.assert_awaited()

    mock_api_client.get_measurements.return_value = None

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.measurements.last_update_success
    assert mock_config_entry.runtime_data.measurements.data is None
    mock_api_client.get_measurements.assert_awaited()

    mock_api_client.get_measurements.return_value = alternative_measurement_response()

    freezer.tick(MEASUREMENTS_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.measurements.last_update_success
    assert (
        mock_config_entry.runtime_data.measurements.data
        == alternative_measurement_response()
    )
    mock_api_client.get_measurements.assert_awaited()


async def test_device_info_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test successful device info update."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(DEVICE_INFO_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.entry_id),
        config_entry_id=mock_config_entry.entry_id,
    )

    assert mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.runtime_data.data == default_info_response()
    mock_api_client.get_device_info.assert_awaited()
    assert device is not None
    assert device.name == DEVICE_NAME
    assert device.model_id == DEVICE_TYPE_NUMBER
    assert device.model == f"{DEVICE_TYPE_LINE} {DEVICE_TYPE_SERIES}"
    assert device.sw_version == FW_VERSION
    assert device.hw_version == HW_VERSION

    mock_api_client.get_device_info.return_value = None

    freezer.tick(DEVICE_INFO_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.entry_id),
        config_entry_id=mock_config_entry.entry_id,
    )

    assert mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.runtime_data.data is None
    mock_api_client.get_device_info.assert_awaited()
    assert device is not None
    assert device.name == DEVICE_NAME
    assert device.model_id == DEVICE_TYPE_NUMBER
    assert device.model == f"{DEVICE_TYPE_LINE} {DEVICE_TYPE_SERIES}"
    assert device.sw_version == FW_VERSION
    assert device.hw_version == HW_VERSION

    mock_api_client.get_device_info.return_value = alternative_info_response()

    freezer.tick(DEVICE_INFO_POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.entry_id),
        config_entry_id=mock_config_entry.entry_id,
    )

    assert mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.runtime_data.data == alternative_info_response()
    mock_api_client.get_device_info.assert_awaited()
    assert device is not None
    assert device.name == ALT_DEVICE_NAME
    assert device.model_id == ALT_DEVICE_TYPE_NUMBER
    assert device.model == f"{DEVICE_TYPE_LINE} {ALT_DEVICE_TYPE_SERIES}"
    assert device.sw_version == ALT_FW_VERSION
    assert device.hw_version == ALT_HW_VERSION


@pytest.mark.parametrize(
    "exception",
    [
        WTCApiDisabledError(),
        WTCApiTemporaryError(),
        WTCApiUnauthorizedError(),
        request_error(),
        http_status_error(503),
    ],
)
async def test_state_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test failed state update because of an exception."""
    mock_api_client.get_state.side_effect = exception

    coordinator = WatercrystStateCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        client=mock_api_client,
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_state_update_failed_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test failed state update because it was cancelled."""
    mock_api_client.get_state.side_effect = CancelledError()

    coordinator = WatercrystStateCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        client=mock_api_client,
    )

    with pytest.raises(CancelledError):
        await coordinator._async_update_data()
