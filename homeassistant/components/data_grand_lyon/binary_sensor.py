"""Binary sensor platform for the Data Grand Lyon integration."""

from data_grand_lyon_ha import VelovStationStatus

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SUBENTRY_TYPE_VELOV_STATION
from .coordinator import DataGrandLyonConfigEntry
from .entity import DataGrandLyonVelovEntity

PARALLEL_UPDATES = 0

VELOV_BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="station_open",
        translation_key="station_open",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DataGrandLyonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Data Grand Lyon binary sensor entities."""
    velov_coordinator = entry.runtime_data.velov_coordinator

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_VELOV_STATION):
        async_add_entities(
            (
                DataGrandLyonVelovBinarySensor(velov_coordinator, subentry, description)
                for description in VELOV_BINARY_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class DataGrandLyonVelovBinarySensor(DataGrandLyonVelovEntity, BinarySensorEntity):
    """Binary sensor for Data Grand Lyon Vélo'v station."""

    @property
    def is_on(self) -> bool:
        """Return true if the station is open."""
        return (
            self.coordinator.data[self._subentry_id].status == VelovStationStatus.OPEN
        )
