"""Tests for WATERCryst update coordinators."""

from copy import copy
from unittest.mock import AsyncMock

from pyocat import (
    WTCApiCancelledError,
    WTCApiDisabledError,
    WTCApiQuotaExceededError,
    WTCApiRequestError,
    WTCApiServerError,
    WTCApiTimeoutError,
    WTCApiUnauthorizedError,
    WTCApiValidationError,
)
from pyocat.models import ModeId
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.components.watercryst.coordinator import (
    DEVICE_INFO_POLLING_INTERVAL,
    MEASUREMENTS_POLLING_INTERVAL,
    STATE_POLLING_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import TriggerPollFunc
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
    assert_state,
    default_info_response,
)


@pytest.mark.usefixtures("setup_integration")
async def test_state_update_success(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    advance_time: TriggerPollFunc,
) -> None:
    """Test successful state update."""
    assert_state(hass, "sensor.ha_device_device_mode", ModeId.WATER_TREATMENT)

    data = copy(mock_api_client.get_state.return_value)
    data.mode.id = ModeId.ERROR_MODE
    mock_api_client.get_state.return_value = data

    await advance_time(STATE_POLLING_INTERVAL)

    # assert_state(hass, "sensor.ha_device_device_mode", ModeId.ERROR_MODE)


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    "exception",
    [
        WTCApiDisabledError,
        WTCApiCancelledError,
        WTCApiQuotaExceededError,
        WTCApiRequestError,
        WTCApiServerError,
        WTCApiTimeoutError,
        WTCApiValidationError,
        WTCApiUnauthorizedError,
    ],
)
async def test_state_update_failed(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    advance_time: TriggerPollFunc,
    exception: type[Exception],
) -> None:
    """Test failed state update because of an exception."""
    mock_api_client.get_state.side_effect = exception()

    await advance_time(STATE_POLLING_INTERVAL)

    for state in hass.states.async_all(domain_filter=Platform.SENSOR):
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_integration")
async def test_measurements_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    advance_time: TriggerPollFunc,
) -> None:
    """Test successful measurements update."""
    for state in hass.states.async_all(domain_filter=Platform.SENSOR):
        assert state.state != STATE_UNAVAILABLE

    mock_api_client.get_measurements.return_value = alternative_measurement_response()

    await advance_time(MEASUREMENTS_POLLING_INTERVAL)

    assert mock_config_entry.runtime_data.measurements.last_update_success
    assert (
        mock_config_entry.runtime_data.measurements.data
        == alternative_measurement_response()
    )
    mock_api_client.get_measurements.assert_awaited()


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    "exception",
    [
        WTCApiDisabledError,
        WTCApiCancelledError,
        WTCApiQuotaExceededError,
        WTCApiRequestError,
        WTCApiServerError,
        WTCApiTimeoutError,
        WTCApiValidationError,
        WTCApiUnauthorizedError,
    ],
)
async def test_measurements_update_failed(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    advance_time: TriggerPollFunc,
    exception: type[Exception],
) -> None:
    """Test failed state update because of an exception."""
    mock_api_client.get_measurements.side_effect = exception()

    await advance_time(MEASUREMENTS_POLLING_INTERVAL)

    for state in hass.states.async_all(domain_filter=DOMAIN):
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_integration")
async def test_device_info_update_success(
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    advance_time: TriggerPollFunc,
) -> None:
    """Test successful device info update."""
    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.unique_id),
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

    mock_api_client.get_device_info.return_value = alternative_info_response()

    await advance_time(DEVICE_INFO_POLLING_INTERVAL)

    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.unique_id),
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


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    "exception",
    [
        WTCApiDisabledError,
        WTCApiCancelledError,
        WTCApiQuotaExceededError,
        WTCApiRequestError,
        WTCApiServerError,
        WTCApiTimeoutError,
        WTCApiValidationError,
        WTCApiUnauthorizedError,
    ],
)
async def test_device_info_update_failed(
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    advance_time: TriggerPollFunc,
    exception: type[Exception],
) -> None:
    """Test failing device info update."""
    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.unique_id),
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

    mock_api_client.get_device_info.side_effect = exception()

    await advance_time(DEVICE_INFO_POLLING_INTERVAL)

    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.unique_id),
        config_entry_id=mock_config_entry.entry_id,
    )

    assert not mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.runtime_data.data == default_info_response()
    mock_api_client.get_device_info.assert_awaited()
    assert device is not None
    assert device.name == DEVICE_NAME
    assert device.model_id == DEVICE_TYPE_NUMBER
    assert device.model == f"{DEVICE_TYPE_LINE} {DEVICE_TYPE_SERIES}"
    assert device.sw_version == FW_VERSION
    assert device.hw_version == HW_VERSION
