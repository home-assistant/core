"""Sensor entities for Tami4Edge."""

import logging

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import API, COORDINATOR, DOMAIN
from .coordinator import Tami4EdgeCoordinator
from .entity import Tami4EdgeBaseEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = [
    SensorEntityDescription(
        key="uv_upcoming_replacement",
        translation_key="uv_upcoming_replacement",
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="uv_installed",
        translation_key="uv_installed",
    ),
    SensorEntityDescription(
        key="filter_upcoming_replacement",
        translation_key="filter_upcoming_replacement",
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="filter_installed",
        translation_key="filter_installed",
    ),
    SensorEntityDescription(
        key="filter_litters_passed",
        translation_key="filter_litters_passed",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Perform the setup for Tami4Edge."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: Tami4EdgeAPI = data[API]
    coordinator: Tami4EdgeCoordinator = data[COORDINATOR]

    async_add_entities(
        Tami4EdgeSensorEntity(
            coordinator=coordinator,
            api=api,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class Tami4EdgeSensorEntity(
    Tami4EdgeBaseEntity,
    CoordinatorEntity[Tami4EdgeCoordinator],
    SensorEntity,
):
    """Representation of the entity."""

    def __init__(
        self,
        coordinator: Tami4EdgeCoordinator,
        api: Tami4EdgeAPI,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the Tami4Edge sensor entity."""
        Tami4EdgeBaseEntity.__init__(self, api, entity_description)
        CoordinatorEntity.__init__(self, coordinator)
        self._update_attr()

    def _update_attr(self) -> None:
        self._attr_native_value = getattr(
            self.coordinator.data, self.entity_description.key
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()
