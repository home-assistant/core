"""Test sensor platform for dk_fuelprices."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch

from homeassistant.components.dk_fuelprices.const import DOMAIN
from homeassistant.components.dk_fuelprices.coordinator import APIClient
from homeassistant.components.dk_fuelprices.sensor import (
    SENSORS,
    BraendstofpriserSensor,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify as util_slugify

from .conftest import TEST_COMPANY, TEST_STATION

from tests.common import MockConfigEntry


class FakeCoordinator:
    """Minimal coordinator used for sensor platform tests."""

    def __init__(self, subentry_id: str) -> None:
        """Initialize fake coordinator data."""
        self.subentry_id = subentry_id
        self.station_name = TEST_STATION["name"]
        self.company = TEST_COMPANY
        self.updated_at: datetime | None = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        self.products: dict[str, dict[str, str | float | None]] = {
            "Blyfri95": {"name": "Blyfri95", "price": 14.29},
            "Blyfri98": {"name": "Blyfri98", "price": 14.99},
        }


async def test_async_setup_entry_creates_sensors(hass: HomeAssistant) -> None:
    """Test sensor setup creates one sensor per product."""
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

    added_entities: list[BraendstofpriserSensor] = []
    add_kwargs: dict = {}

    def _async_add_entities(entities, *_args, **kwargs) -> None:
        added_entities.extend(entities)
        add_kwargs.update(kwargs)

    await async_setup_entry(
        hass,
        config_entry,
        cast(AddConfigEntryEntitiesCallback, _async_add_entities),
    )

    assert len(added_entities) == 2
    assert add_kwargs["config_subentry_id"] == coordinator.subentry_id

    slugified_subentry_id = util_slugify(subentry_id)
    unique_ids = {entity.unique_id for entity in added_entities}
    assert unique_ids == {
        f"{slugified_subentry_id}_price_blyfri95",
        f"{slugified_subentry_id}_price_blyfri98",
    }

    product_entity = next(
        entity for entity in added_entities if entity.name == "Blyfri95"
    )

    assert product_entity.native_value == 14.29
    assert product_entity.device_info is not None
    assert product_entity.device_info["identifiers"] == {(DOMAIN, subentry_id)}


async def test_async_setup_entry_removes_stale_registry_entries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test stale entities and devices are removed during setup."""
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

    entity_registry = er.async_get(hass)
    stale_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "station_1_price_obsolete",
        config_entry=config_entry,
        original_name="Obsolete",
        config_subentry_id=coordinator.subentry_id,
    )

    stale_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.subentry_id)},
        name="Stale device",
    )

    await async_setup_entry(hass, config_entry, lambda *_args, **_kwargs: None)

    assert entity_registry.async_get(stale_entity.entity_id) is None
    assert device_registry.async_get(stale_device.id) is None


async def test_async_setup_entry_skips_other_subentry_registry_entries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup keeps entities/devices from other subentries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Circle K - Aarhus C",
                unique_id="Circle K_1234",
                data={},
            ),
            ConfigSubentryData(
                subentry_type="station",
                title="Circle K - Aarhus N",
                unique_id="Circle K_4321",
                data={},
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    subentry_ids = list(config_entry.subentries)
    first_subentry_id = subentry_ids[0]
    second_subentry_id = subentry_ids[1]
    coordinator = FakeCoordinator(first_subentry_id)
    config_entry.runtime_data = {coordinator.subentry_id: coordinator}

    entity_registry = er.async_get(hass)
    other_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{second_subentry_id}_price_obsolete",
        config_entry=config_entry,
        original_name="Other station entity",
        config_subentry_id=second_subentry_id,
    )
    other_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, second_subentry_id)},
        name="Other station device",
    )

    await async_setup_entry(hass, config_entry, lambda *_args, **_kwargs: None)

    assert entity_registry.async_get(other_entity.entity_id) is not None
    assert device_registry.async_get(other_device.id) is not None


async def test_sensor_updates_value_only_when_new_value_is_not_none() -> None:
    """Test sensor value update behavior on coordinator updates."""
    coordinator = FakeCoordinator("station_1")
    price_description = next(
        description for description in SENSORS if description.key == "price"
    )

    sensor = BraendstofpriserSensor(
        cast(APIClient, coordinator), "Blyfri95", "Blyfri95", price_description
    )
    with patch.object(sensor, "schedule_update_ha_state") as schedule_mock:
        assert sensor.native_value == 14.29

        coordinator.products["Blyfri95"]["price"] = None
        sensor._handle_coordinator_update()

        assert sensor.native_value == 14.29
        assert schedule_mock.call_count == 1

        coordinator.products["Blyfri95"]["price"] = 15.01
        sensor._handle_coordinator_update()

        assert sensor.native_value == 15.01
        assert schedule_mock.call_count == 2
