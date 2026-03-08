"""Fixtures for the Kaiterra integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.kaiterra.api_data import (
    KaiterraApiAuthError,
    KaiterraApiError,
    KaiterraDeviceNotFoundError,
)
from homeassistant.components.kaiterra.const import (
    CONF_AQI_STANDARD,
    DEFAULT_AQI_STANDARD,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_NAME

from tests.common import MockConfigEntry

API_KEY = "test-api-key"
DEVICE_ID = "device-123"
DEVICE_NAME = "Office"
DEVICE_ID_2 = "device-456"
DEVICE_NAME_2 = "Bedroom"

MOCK_DEVICE_DATA = {
    "aqi": {"value": 78},
    "aqi_level": {"value": "Moderate"},
    "aqi_pollutant": {"value": "TVOC"},
    "rtemp": {"value": 72.3, "unit": "F"},
    "rhumid": {"value": 18.8, "unit": "%"},
    "rpm25c": {"value": 1, "unit": "μg/m³"},
    "rpm10c": {"value": 2, "unit": "μg/m³"},
    "rco2": {"value": 407, "unit": "ppm"},
    "tvoc": {"value": 127, "unit": "ppb"},
}

MOCK_DEVICE_DATA_2 = {
    "aqi": {"value": 55},
    "aqi_level": {"value": "Moderate"},
    "aqi_pollutant": {"value": "PM2.5"},
    "rtemp": {"value": 69.0, "unit": "F"},
    "rhumid": {"value": 42.0, "unit": "%"},
    "rpm25c": {"value": 5, "unit": "μg/m³"},
    "rpm10c": {"value": 8, "unit": "μg/m³"},
    "rco2": {"value": 520, "unit": "ppm"},
    "tvoc": {"value": 91, "unit": "ppb"},
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Kaiterra config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEVICE_NAME,
        unique_id=DEVICE_ID,
        data={
            CONF_API_KEY: API_KEY,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_NAME: DEVICE_NAME,
        },
        options={CONF_AQI_STANDARD: DEFAULT_AQI_STANDARD},
    )


@pytest.fixture
def mock_config_entry_2() -> MockConfigEntry:
    """Return a second Kaiterra config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEVICE_NAME_2,
        unique_id=DEVICE_ID_2,
        data={
            CONF_API_KEY: API_KEY,
            CONF_DEVICE_ID: DEVICE_ID_2,
            CONF_NAME: DEVICE_NAME_2,
        },
        options={CONF_AQI_STANDARD: DEFAULT_AQI_STANDARD},
    )


@pytest.fixture
def mock_kaiterra_device_data() -> AsyncMock:
    """Mock successful Kaiterra device reads."""
    with patch(
        "homeassistant.components.kaiterra.api_data."
        "KaiterraApiClient.async_get_latest_sensor_readings",
        new=AsyncMock(return_value=MOCK_DEVICE_DATA),
    ) as mock_readings:
        yield mock_readings


@pytest.fixture
def mock_kaiterra_device_data_multiple() -> AsyncMock:
    """Mock successful Kaiterra reads for two devices."""

    async def _side_effect(device_id: str):
        if device_id == DEVICE_ID:
            return MOCK_DEVICE_DATA
        if device_id == DEVICE_ID_2:
            return MOCK_DEVICE_DATA_2
        raise KaiterraDeviceNotFoundError(device_id)

    with patch(
        "homeassistant.components.kaiterra.api_data."
        "KaiterraApiClient.async_get_latest_sensor_readings",
        new=AsyncMock(side_effect=_side_effect),
    ) as mock_readings:
        yield mock_readings


@pytest.fixture
def mock_kaiterra_auth_error() -> AsyncMock:
    """Mock Kaiterra authentication failure."""
    with patch(
        "homeassistant.components.kaiterra.api_data."
        "KaiterraApiClient.async_get_latest_sensor_readings",
        new=AsyncMock(side_effect=KaiterraApiAuthError),
    ) as mock_readings:
        yield mock_readings


@pytest.fixture
def mock_kaiterra_api_error() -> AsyncMock:
    """Mock Kaiterra connectivity failure."""
    with patch(
        "homeassistant.components.kaiterra.api_data."
        "KaiterraApiClient.async_get_latest_sensor_readings",
        new=AsyncMock(side_effect=KaiterraApiError),
    ) as mock_readings:
        yield mock_readings


@pytest.fixture
def mock_kaiterra_device_not_found() -> AsyncMock:
    """Mock Kaiterra missing-device failure."""
    with patch(
        "homeassistant.components.kaiterra.api_data."
        "KaiterraApiClient.async_get_latest_sensor_readings",
        new=AsyncMock(side_effect=KaiterraDeviceNotFoundError(DEVICE_ID)),
    ) as mock_readings:
        yield mock_readings
