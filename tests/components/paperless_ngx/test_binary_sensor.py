"""Tests for Paperless-ngx binary sensor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.paperless_ngx.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    PaperlessBinarySensor,
    PaperlessBinarySensorEntityDescription,
    async_setup_entry,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


@pytest.mark.asyncio
async def test_async_setup_entry_adds_all_binary_entities(hass: HomeAssistant) -> None:
    """Test that all PaperlessBinarySensor entities are added."""

    mock_entry = MagicMock()
    mock_entry.entry_id = "mock_entry"
    mock_entry.runtime_data = MagicMock()

    add_entities_mock: AddConfigEntryEntitiesCallback = AsyncMock()

    await async_setup_entry(hass, mock_entry, add_entities_mock)

    add_entities_mock.assert_called_once()
    added_entities = add_entities_mock.call_args[0][0]

    assert len(added_entities) == len(BINARY_SENSOR_DESCRIPTIONS)
    for entity in added_entities:
        assert isinstance(entity, PaperlessBinarySensor)
        assert entity.coordinator == mock_entry.runtime_data
        assert entity.entry == mock_entry
        assert entity.entity_description in BINARY_SENSOR_DESCRIPTIONS


@pytest.mark.asyncio
async def test_paperless_binary_sensor_is_on_true() -> None:
    """Test PaperlessBinarySensor is_on returns True."""

    description = PaperlessBinarySensorEntityDescription(
        key="test_binary_sensor",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: True,
    )

    coordinator = MagicMock()

    sensor = PaperlessBinarySensor(
        entry=MagicMock(entry_id="123"),
        coordinator=coordinator,
        description=description,
    )

    assert sensor.is_on is True
    assert sensor.available is True


@pytest.mark.asyncio
async def test_paperless_binary_sensor_is_on_false() -> None:
    """Test PaperlessBinarySensor is_on returns False."""

    description = PaperlessBinarySensorEntityDescription(
        key="test_binary_sensor",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: False,
    )

    coordinator = MagicMock()

    sensor = PaperlessBinarySensor(
        entry=MagicMock(entry_id="123"),
        coordinator=coordinator,
        description=description,
    )

    assert sensor.is_on is False
    assert sensor.available is True


@pytest.mark.asyncio
async def test_paperless_binary_sensor_is_on_none() -> None:
    """Test PaperlessBinarySensor handles None value."""

    description = PaperlessBinarySensorEntityDescription(
        key="test_binary_sensor",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None,
    )

    coordinator = MagicMock()

    sensor = PaperlessBinarySensor(
        entry=MagicMock(entry_id="123"),
        coordinator=coordinator,
        description=description,
    )

    assert sensor.is_on is None
    assert sensor.available is False


@pytest.mark.asyncio
async def test_paperless_binary_sensor_handle_coordinator_update_value_change() -> None:
    """Test _handle_coordinator_update reflects updated value from coordinator."""

    state = False

    description = PaperlessBinarySensorEntityDescription(
        key="test_binary_sensor",
        value_fn=lambda data: data["value"],
    )

    coordinator = MagicMock()
    coordinator.data = {"value": state}

    sensor = PaperlessBinarySensor(
        entry=MagicMock(entry_id="123"),
        coordinator=coordinator,
        description=description,
    )

    assert sensor.is_on is False
    assert sensor.available is True

    sensor.async_write_ha_state = MagicMock()

    coordinator.data = {"value": True}

    sensor._handle_coordinator_update()

    sensor.async_write_ha_state.assert_called_once()
    assert sensor.is_on is True
    assert sensor.available is True
