"""Tests for the Prana sensor platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.prana.const import DOMAIN, PranaSensorType
from homeassistant.components.prana.sensor import PranaSensor, async_setup_entry
from homeassistant.core import HomeAssistant


@pytest.fixture
def coordinator(hass: HomeAssistant):
    """Mock coordinator for tests."""
    coord = MagicMock()
    coord.data = {
        PranaSensorType.INSIDE_TEMPERATURE: 21.5,
        PranaSensorType.OUTSIDE_TEMPERATURE: 15.2,
        PranaSensorType.HUMIDITY: 45,
    }
    coord.async_refresh = AsyncMock()
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    return coord


@pytest.fixture
def config_entry(hass: HomeAssistant):
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_sensor_entry"
    entry.data = {"host": "127.0.0.1", "name": "Prana Device"}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}
    return entry


@pytest.fixture
def device_info(config_entry):
    """Device info matching sensor platform."""
    return {
        "identifiers": {(DOMAIN, config_entry.entry_id)},
        "name": config_entry.data.get("name", "Prana Device"),
        "manufacturer": "Prana",
        "model": "PRANA RECUPERATOR",
    }


async def test_sensor_properties(
    coordinator: MagicMock, config_entry: MagicMock, device_info: dict
) -> None:
    """Test sensor entity properties and icons."""
    temp_in = PranaSensor(
        "id1",
        "Inside Temperature",
        coordinator,
        "inside_temperature",
        device_info,
        PranaSensorType.INSIDE_TEMPERATURE,
    )
    assert temp_in.native_value == 21.5
    assert temp_in.available is True
    assert temp_in.icon == "mdi:home-thermometer"

    humidity = PranaSensor(
        "id2",
        "Humidity",
        coordinator,
        "humidity",
        device_info,
        PranaSensorType.HUMIDITY,
    )
    assert humidity.native_value == 45
    assert humidity.available is True
    assert humidity.icon == "mdi:water-percent"


async def test_sensor_availability(
    coordinator: MagicMock, config_entry: MagicMock, device_info: dict
) -> None:
    """Test availability reflects coordinator data."""
    sensor = PranaSensor(
        "id3",
        "Outside Temperature",
        coordinator,
        "outside_temperature",
        device_info,
        PranaSensorType.OUTSIDE_TEMPERATURE,
    )
    assert sensor.available is True

    # None means unavailable per implementation
    coordinator.data[PranaSensorType.OUTSIDE_TEMPERATURE] = None
    assert sensor.available is False


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, coordinator: AsyncMock, config_entry: MagicMock
) -> None:
    """Test setup entry for sensor platform."""
    coordinator = AsyncMock()
    coordinator.data = {
        PranaSensorType.INSIDE_TEMPERATURE: 21.5,
        PranaSensorType.OUTSIDE_TEMPERATURE: 15.2,
        PranaSensorType.INSIDE_TEMPERATURE_2: None,  # skipped
        PranaSensorType.OUTSIDE_TEMPERATURE_2: None,  # skipped
        PranaSensorType.HUMIDITY: 45,
        PranaSensorType.VOC: None,  # skipped
        PranaSensorType.AIR_PRESSURE: None,  # skipped
        PranaSensorType.CO2: None,  # skipped
    }
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    added = []

    def async_add_entities(entities, update_before_add: bool = False):
        added.extend(entities)

    await async_setup_entry(hass, config_entry, async_add_entities)

    # Only non-None entries are added
    assert len(added) == 3
    assert all(isinstance(sensor, PranaSensor) for sensor in added)
    types = {s.sensor_type for s in added}
    assert types == {
        PranaSensorType.INSIDE_TEMPERATURE,
        PranaSensorType.OUTSIDE_TEMPERATURE,
        PranaSensorType.HUMIDITY,
    }
