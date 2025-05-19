"""Tests for Paperless-ngx sensor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.paperless_ngx.sensor import (
    SENSOR_DESCRIPTIONS,
    PaperlessEntityDescription,
    PaperlessSensor,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .conftest import TestEnum


@pytest.mark.asyncio
async def test_async_setup_entry_adds_all_entities(hass: HomeAssistant) -> None:
    """Test that all PaperlessSensor entities are added."""

    mock_data = MagicMock()
    mock_data.coordinator.data = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "mock_entry"
    mock_entry.runtime_data = mock_data

    add_entities_mock: AddConfigEntryEntitiesCallback = AsyncMock()

    await async_setup_entry(hass, mock_entry, add_entities_mock)

    add_entities_mock.assert_called_once()
    added_entities = add_entities_mock.call_args[0][0]

    assert len(added_entities) == len(SENSOR_DESCRIPTIONS)
    for entity in added_entities:
        assert isinstance(entity, PaperlessSensor)
        assert entity.coordinator == mock_data.coordinator
        assert entity.entry == mock_entry
        assert entity.entity_description in SENSOR_DESCRIPTIONS


@pytest.mark.asyncio
async def test_paperless_sensor_behavior_fn_value_none() -> None:
    """Test that PaperlessSensor handles fn_value None correctly."""

    description = PaperlessEntityDescription(
        key="test_sensor",
        value_fn=None,
        attributes_fn=None,
    )

    coordinator = MagicMock()
    coordinator.data = MagicMock()

    sensor = PaperlessSensor(
        coordinator=coordinator,
        data=MagicMock(),
        entry=MagicMock(entry_id="123"),
        description=description,
    )

    assert sensor.native_value is None
    assert sensor.available is False


@pytest.mark.asyncio
async def test_paperless_sensor_behavior_enum_value() -> None:
    """Test that PaperlessSensor handles enum values correctly."""

    description = PaperlessEntityDescription(
        key="test_sensor",
        value_fn=lambda data: TestEnum("Alpha"),
        attributes_fn=None,
    )

    coordinator = MagicMock()
    coordinator.data = MagicMock()

    sensor = PaperlessSensor(
        coordinator=coordinator,
        data=MagicMock(),
        entry=MagicMock(entry_id="123"),
        description=description,
    )

    assert sensor.native_value == "alpha"
    assert sensor.available is True


@pytest.mark.asyncio
async def test_paperless_sensor_behavior_plain_value() -> None:
    """Test that PaperlessSensor handles plain values correctly."""

    description = PaperlessEntityDescription(
        key="test_sensor",
        value_fn=lambda data: 123,
        attributes_fn=None,
    )

    coordinator = MagicMock()
    coordinator.data = MagicMock()

    sensor = PaperlessSensor(
        coordinator=coordinator,
        data=MagicMock(),
        entry=MagicMock(entry_id="123"),
        description=description,
    )

    assert sensor.native_value == 123
    assert sensor.available is True


@pytest.mark.asyncio
async def test_paperless_sensor_behavior_none_value() -> None:
    """Test that PaperlessSensor handles None value properly."""

    description = PaperlessEntityDescription(
        key="test_sensor",
        value_fn=lambda data: None,
        attributes_fn=None,
    )

    coordinator = MagicMock()
    coordinator.data = MagicMock()

    sensor = PaperlessSensor(
        coordinator=coordinator,
        data=MagicMock(),
        entry=MagicMock(entry_id="123"),
        description=description,
    )

    assert sensor.native_value is None
    assert sensor.available is False


@pytest.mark.asyncio
async def test_paperless_sensor_extra_attributes() -> None:
    """Test extra_state_attributes when attributes_fn is set."""

    description = PaperlessEntityDescription(
        key="test_sensor",
        value_fn=lambda data: 42,
        attributes_fn=lambda data: {
            "test_attr": "value",
            "error": None,
        },
    )

    coordinator = MagicMock()
    coordinator.data = MagicMock()

    sensor = PaperlessSensor(
        coordinator=coordinator,
        data=MagicMock(),
        entry=MagicMock(entry_id="123"),
        description=description,
    )

    attrs = sensor.extra_state_attributes
    assert attrs == {
        "test_attr": "value",
        "error": None,
    }


@pytest.mark.asyncio
async def test_paperless_sensor_handle_coordinator_update_value_change() -> None:
    """Test _handle_coordinator_update reflects updated value from coordinator."""

    test_value = 1

    description = PaperlessEntityDescription(
        key="test_sensor",
        value_fn=lambda data: test_value,
    )

    coordinator = MagicMock()
    coordinator.data = test_value

    sensor = PaperlessSensor(
        coordinator=coordinator,
        data=MagicMock(),
        entry=MagicMock(entry_id="123"),
        description=description,
    )

    assert sensor.native_value == 1
    assert sensor.available is True

    sensor.async_write_ha_state = MagicMock()

    test_value = 999

    sensor._handle_coordinator_update()

    sensor.async_write_ha_state.assert_called_once()

    assert sensor.native_value == 999
    assert sensor.available is True
