"""Test sensor platform for Fuelprices.dk."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch

from homeassistant.components.fuelprices_dk.const import DOMAIN
from homeassistant.components.fuelprices_dk.coordinator import APIClient
from homeassistant.components.fuelprices_dk.sensor import (
    SENSORS,
    FuelpricesDkSensor,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .conftest import TEST_COMPANY, TEST_STATION

from tests.common import MockConfigEntry


class FakeCoordinator:
    """Minimal coordinator used for sensor platform tests."""

    def __init__(self, subentry_id: str) -> None:
        """Initialize fake coordinator data."""
        self.subentry_id = subentry_id
        self.station_id = TEST_STATION["id"]
        self.station_name = TEST_STATION["name"]
        self.company = TEST_COMPANY
        self.last_update_success = True
        self.updated_at: datetime | None = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        self.products: dict[str, dict[str, str | float | None]] = {
            "Blyfri95": {"name": "Blyfri95", "price": 14.29},
            "Blyfri98": {"name": "Blyfri98", "price": 14.99},
        }


async def test_async_setup_entry_creates_sensors(hass: HomeAssistant) -> None:
    """Test sensor setup creates one sensor per product and diagnostics."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Circle K - Aarhus C",
                unique_id="Circle K_1234",
                data={},
            )
        ],
    )
    config_entry.add_to_hass(hass)

    subentry_id = next(iter(config_entry.subentries))
    coordinator = FakeCoordinator(subentry_id)
    config_entry.runtime_data = {coordinator.subentry_id: coordinator}

    added_entities: list[FuelpricesDkSensor] = []
    add_kwargs: dict[str, str] = {}

    def _async_add_entities(entities, *_args, **kwargs) -> None:
        added_entities.extend(entities)
        add_kwargs.update(kwargs)

    await async_setup_entry(
        hass,
        config_entry,
        cast(AddConfigEntryEntitiesCallback, _async_add_entities),
    )

    assert len(added_entities) == 3
    assert add_kwargs["config_subentry_id"] == coordinator.subentry_id
    assert {entity.unique_id for entity in added_entities} == {
        f"{TEST_STATION['id']}_last_updated_last_updated",
        f"{TEST_STATION['id']}_price_blyfri95",
        f"{TEST_STATION['id']}_price_blyfri98",
    }

    product_entity = next(
        entity for entity in added_entities if entity.name == "Blyfri95"
    )

    assert product_entity.native_value == 14.29
    assert product_entity.device_info is not None
    assert product_entity.device_info["identifiers"] == {
        (DOMAIN, str(TEST_STATION["id"]))
    }
    assert product_entity.device_info["entry_type"] is DeviceEntryType.SERVICE
    assert product_entity.device_class is None

    last_updated_entity = next(
        entity for entity in added_entities if entity.name == "Last Updated"
    )

    assert last_updated_entity.native_value == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    assert last_updated_entity.entity_category is not None


async def test_sensor_available_follows_product_presence() -> None:
    """Test sensor availability follows the fetched products."""
    coordinator = FakeCoordinator("station_1")
    price_description = next(
        description for description in SENSORS if description.key == "price"
    )

    sensor = FuelpricesDkSensor(
        cast(APIClient, coordinator),
        coordinator.station_name,
        "Blyfri95",
        "Blyfri95",
        price_description,
    )

    assert sensor.available is True
    assert sensor.native_value == 14.29

    coordinator.products.pop("Blyfri95")

    assert sensor.available is False
    assert sensor.native_value is None


async def test_last_updated_sensor_uses_coordinator_timestamp() -> None:
    """Test the last updated sensor exposes coordinator timestamp data."""
    coordinator = FakeCoordinator("station_1")
    last_updated_description = next(
        description for description in SENSORS if description.key == "last_updated"
    )

    sensor = FuelpricesDkSensor(
        cast(APIClient, coordinator),
        coordinator.station_name,
        "last_updated",
        "Last Updated",
        last_updated_description,
    )

    assert sensor.available is True
    assert sensor.native_value == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

    coordinator.updated_at = None

    assert sensor.available is True
    assert sensor.native_value is None


async def test_sensor_writes_state_on_coordinator_update() -> None:
    """Test sensor writes state when coordinator data changes."""
    coordinator = FakeCoordinator("station_1")
    price_description = next(
        description for description in SENSORS if description.key == "price"
    )

    sensor = FuelpricesDkSensor(
        cast(APIClient, coordinator),
        coordinator.station_name,
        "Blyfri95",
        "Blyfri95",
        price_description,
    )
    with patch.object(sensor, "async_write_ha_state") as write_state_mock:
        sensor._handle_coordinator_update()

    write_state_mock.assert_called_once()
