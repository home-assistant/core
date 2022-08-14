"""Sensor entities for Tami4Edge."""
from datetime import timedelta
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
    UpdateFailed,
)

from . import Tami4EdgeBaseEntity
from .const import DOMAIN

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


class Tami4EdgeWaterQualityCoordinator(DataUpdateCoordinator):
    """Tami4Edge water quality coordinator."""

    def __init__(self, hass: HomeAssistant, edge: Tami4EdgeAPI) -> None:
        """Initialize the water quality coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tami4Edge water quality coordinator",
            update_interval=timedelta(minutes=10),
        )
        self.edge = edge

    async def _async_update_data(self) -> dict:
        """Fetch data from the API endpoint."""
        try:
            water_quality = await self.hass.async_add_executor_job(
                self.edge.get_water_quality
            )
            return {
                "uv_last_replacement": water_quality.uv.last_replacement,
                "uv_upcoming_replacement": water_quality.uv.upcoming_replacement,
                "uv_status": water_quality.uv.status,
                "filter_last_replacement": water_quality.filter.last_replacement,
                "filter_upcoming_replacement": water_quality.filter.upcoming_replacement,
                "filter_status": water_quality.filter.status,
                "filter_milli_litters_passed": water_quality.filter.milli_litters_passed,
            }
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with API: {ex}") from ex


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
