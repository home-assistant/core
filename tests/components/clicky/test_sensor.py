"""Tests for the Clicky sensor platform."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.components.clicky.sensor import SENSOR_TYPES, ClickySensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that async_setup_entry creates the expected sensors."""

    mock_data = {
        "visitorsOnline": 42,
        "timeTotal": 3600,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: "12345",
            CONF_SITEKEY: "abcdef",
        },
    )

    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.clicky.coordinator.ClickyCoordinator._async_update_data",
        AsyncMock(return_value=mock_data),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entities = [
            entity
            for entity in entity_registry.entities.values()
            if entity.platform == DOMAIN
        ]

        assert len(entities) == len(SENSOR_TYPES)

        assert entities[0].unique_id == "12345_visitorsOnline"
        assert entities[1].unique_id == "12345_timeTotal"


def test_sensor_native_value() -> None:
    """Test native_value returns coordinator data."""

    coordinator = Mock()
    coordinator.data = {
        "visitorsOnline": 42,
        "timeTotal": 3600,
    }

    visitors = ClickySensor(
        coordinator=coordinator,
        description=SENSOR_TYPES[0],
        site_id=12345,
    )

    total_time = ClickySensor(
        coordinator=coordinator,
        description=SENSOR_TYPES[1],
        site_id=12345,
    )

    assert visitors.native_value == 42
    assert total_time.native_value == 3600


def test_sensor_missing_data() -> None:
    """Test missing coordinator data returns None."""

    coordinator = Mock()
    coordinator.data = None

    sensor = ClickySensor(
        coordinator=coordinator,
        description=SENSOR_TYPES[0],
        site_id=12345,
    )

    assert sensor.native_value is None


def test_sensor_missing_key() -> None:
    """Test missing coordinator key returns None."""

    coordinator = Mock()
    coordinator.data = {}

    sensor = ClickySensor(
        coordinator=coordinator,
        description=SENSOR_TYPES[0],
        site_id=12345,
    )

    assert sensor.native_value is None


def test_sensor_attributes() -> None:
    """Test static sensor attributes."""

    coordinator = Mock()
    coordinator.data = {}

    sensor = ClickySensor(
        coordinator=coordinator,
        description=SENSOR_TYPES[0],
        site_id=12345,
    )

    assert sensor.unique_id == "12345_visitorsOnline"
    assert sensor.entity_description.name == "Visitors Online"
