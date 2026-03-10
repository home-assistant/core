"""Fixtures for Kaiterra tests."""

from __future__ import annotations

from collections.abc import Generator
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.kaiterra.api_data import (
    KaiterraApiAuthError,
    KaiterraDeviceNotFoundError,
)
from homeassistant.components.kaiterra.const import (
    CONF_AQI_STANDARD,
    CONF_PREFERRED_UNITS,
    DEFAULT_AQI_STANDARD,
    DEFAULT_PREFERRED_UNIT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)

from tests.common import MockConfigEntry

API_KEY = "test-api-key"
NEW_API_KEY = "new-api-key"
DEVICE_ID = "device-123"
DEVICE_NAME = "Office"
DEVICE_TYPE = "sensedge"
DEVICE_ID_2 = "device-456"
DEVICE_NAME_2 = "Bedroom"
DEVICE_TYPE_2 = "laseregg"

RAW_DEVICE_PAYLOAD = {
    "rtemp": {"points": [{"value": 72.3}], "units": "F"},
    "rhumid": {"points": [{"value": 18.8}], "units": "%"},
    "rpm25c": {"points": [{"value": 1, "aqi": 78}], "units": "μg/m³"},
    "rpm10c": {"points": [{"value": 2, "aqi": 55}], "units": "μg/m³"},
    "rco2": {"points": [{"value": 407}], "units": "ppm"},
    "tvoc": {"points": [{"value": 127, "aqi": 60}], "units": "ppb"},
}

RAW_DEVICE_PAYLOAD_2 = {
    "rtemp": {"points": [{"value": 69.0}], "units": "F"},
    "rhumid": {"points": [{"value": 42.0}], "units": "%"},
    "rpm25c": {"points": [{"value": 5, "aqi": 55}], "units": "μg/m³"},
    "rpm10c": {"points": [{"value": 8, "aqi": 35}], "units": "μg/m³"},
    "rco2": {"points": [{"value": 520}], "units": "ppm"},
    "tvoc": {"points": [{"value": 91, "aqi": 44}], "units": "ppb"},
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Kaiterra parent config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Kaiterra",
        data={CONF_API_KEY: API_KEY},
        options={
            CONF_AQI_STANDARD: DEFAULT_AQI_STANDARD,
            CONF_PREFERRED_UNITS: DEFAULT_PREFERRED_UNIT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
        },
    )


@pytest.fixture
def mock_validate_device() -> Generator[AsyncMock]:
    """Mock successful device validation."""
    with patch(
        "homeassistant.components.kaiterra.api_data.KaiterraApiClient.async_validate_device",
        new=AsyncMock(return_value=None),
    ) as mock_validate:
        yield mock_validate


@pytest.fixture
def mock_validate_device_auth_error() -> Generator[AsyncMock]:
    """Mock auth failure during device validation."""
    with patch(
        "homeassistant.components.kaiterra.api_data.KaiterraApiClient.async_validate_device",
        new=AsyncMock(side_effect=KaiterraApiAuthError("Invalid Kaiterra API key")),
    ) as mock_validate:
        yield mock_validate


@pytest.fixture
def mock_validate_device_not_found() -> Generator[AsyncMock]:
    """Mock missing device during validation."""
    with patch(
        "homeassistant.components.kaiterra.api_data.KaiterraApiClient.async_validate_device",
        new=AsyncMock(side_effect=KaiterraDeviceNotFoundError("Device not found")),
    ) as mock_validate:
        yield mock_validate


@pytest.fixture
def mock_latest_sensor_readings() -> Generator[AsyncMock]:
    """Mock successful sensor reads for configured devices."""

    async def _side_effect(paths: list[str]):
        payloads = []
        for path in paths:
            if DEVICE_ID in path:
                payloads.append(RAW_DEVICE_PAYLOAD)
            elif DEVICE_ID_2 in path:
                payloads.append(RAW_DEVICE_PAYLOAD_2)
            else:
                payloads.append(None)
        return payloads

    with patch(
        "homeassistant.components.kaiterra.api_data.KaiterraAPIClient.get_latest_sensor_readings",
        new=AsyncMock(side_effect=_side_effect),
    ) as mock_readings:
        yield mock_readings


def add_device_subentry(
    hass,
    entry: MockConfigEntry,
    device_id: str = DEVICE_ID,
    device_type: str = DEVICE_TYPE,
    name: str | None = DEVICE_NAME,
) -> ConfigSubentry:
    """Attach a Kaiterra device subentry to a config entry."""
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)

    data = {
        CONF_DEVICE_ID: device_id,
        CONF_TYPE: device_type,
    }
    if name is not None:
        data[CONF_NAME] = name

    subentry = ConfigSubentry(
        subentry_type=SUBENTRY_TYPE_DEVICE,
        title=name or device_id,
        unique_id=f"{device_type}_{device_id}",
        data=MappingProxyType(data),
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    return subentry
