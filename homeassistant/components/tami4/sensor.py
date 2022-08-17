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
from homeassistant.const import VOLUME_MILLILITERS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import Tami4EdgeBaseEntity
from .const import DOMAIN
from .coordinator import Tami4EdgeWaterQualityCoordinator

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTIONS = [
    SensorEntityDescription(
        key="uv_last_replacement",
        name="UV Last Replacement",
        icon="mdi:calendar",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="uv_upcoming_replacement",
        name="UV Upcoming Replacement",
        icon="mdi:calendar",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="uv_status",
        name="UV Status",
        icon="mdi:clipboard-check-multiple",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="filter_last_replacement",
        name="Filter Last Replacement",
        icon="mdi:calendar",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="filter_upcoming_replacement",
        name="Filter Upcoming Replacement",
        icon="mdi:calendar",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="filter_status",
        name="Filter Status",
        icon="mdi:clipboard-check-multiple",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="filter_milli_litters_passed",
        name="Filter Water Passed",
        native_unit_of_measurement=VOLUME_MILLILITERS,
        icon="mdi:water",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Perform the setup for Tami4Edge."""
    edge = hass.data[DOMAIN][entry.entry_id]

    try:
        coordinator = Tami4EdgeWaterQualityCoordinator(hass, edge)

        entities = []
        for entity_description in ENTITY_DESCRIPTIONS:
            entities.append(
                Tami4EdgeSensorEntity(
                    coordinator=coordinator,
                    edge=edge,
                    entity_description=entity_description,
                )
            )

        async_add_entities(entities)
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        _LOGGER.exception("Fail to setup Tami4Edge")
        raise ex


class Tami4EdgeSensorEntity(Tami4EdgeBaseEntity, CoordinatorEntity, SensorEntity):
    """Representation of the entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        edge: Tami4EdgeAPI,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the Tami4Edge entity."""
        Tami4EdgeBaseEntity.__init__(self, edge, entity_description)
        CoordinatorEntity.__init__(self, coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self.coordinator.data[self.entity_description.key]
        except KeyError:
            return
        self.async_write_ha_state()
