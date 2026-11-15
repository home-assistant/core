"""Compensation fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.compensation.const import (
    CONF_COMPENSATED_VALUE,
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_POLYNOMIAL_CONFIG,
    CONF_PRECISION,
    CONF_UNCOMPENSATED_VALUE,
    CONF_UPPER_LIMIT,
    DOMAIN,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.compensation.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def data_points() -> list[dict[str, float]]:
    """Return the data points for the config entry."""
    return [
        {CONF_UNCOMPENSATED_VALUE: 1.0, CONF_COMPENSATED_VALUE: 2.0},
        {CONF_UNCOMPENSATED_VALUE: 2.0, CONF_COMPENSATED_VALUE: 3.0},
    ]


@pytest.fixture
def mock_config_entry(data_points: list[dict[str, float]]) -> MockConfigEntry:
    """Return a compensation config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My compensation",
        options={
            CONF_NAME: "My compensation",
            CONF_ENTITY_ID: "sensor.uncompensated",
            CONF_POLYNOMIAL_CONFIG: {
                CONF_DATAPOINTS: data_points,
                CONF_DEGREE: 1,
            },
            CONF_LOWER_LIMIT: False,
            CONF_UPPER_LIMIT: False,
            CONF_PRECISION: 2,
        },
    )


@pytest.fixture
def sensor_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the config entry of the source sensor."""
    sensor_config_entry = MockConfigEntry()
    sensor_config_entry.add_to_hass(hass)
    return sensor_config_entry


@pytest.fixture
def sensor_device(
    device_registry: dr.DeviceRegistry, sensor_config_entry: MockConfigEntry
) -> dr.DeviceEntry:
    """Return the device of the source sensor."""
    return device_registry.async_get_or_create(
        config_entry_id=sensor_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )


@pytest.fixture
def sensor_entity_entry(
    entity_registry: er.EntityRegistry,
    sensor_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Return the source sensor entity entry, linked to the source device."""
    return entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique",
        config_entry=sensor_config_entry,
        device_id=sensor_device.id,
        suggested_object_id="uncompensated",
    )
