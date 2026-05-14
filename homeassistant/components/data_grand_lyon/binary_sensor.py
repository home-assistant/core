"""Binary sensor platform for the Data Grand Lyon integration."""

from data_grand_lyon_ha import VelovStationStatus

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SUBENTRY_TYPE_VELOV_STATION
from .coordinator import DataGrandLyonConfigEntry, DataGrandLyonCoordinator

PARALLEL_UPDATES = 0

VELOV_BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="station_open",
        translation_key="station_open",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DataGrandLyonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Data Grand Lyon binary sensor entities."""
    coordinator = entry.runtime_data

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_VELOV_STATION):
        async_add_entities(
            (
                DataGrandLyonVelovBinarySensor(coordinator, subentry, description)
                for description in VELOV_BINARY_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class DataGrandLyonVelovBinarySensor(
    CoordinatorEntity[DataGrandLyonCoordinator], BinarySensorEntity
):
    """Binary sensor for Data Grand Lyon Vélo'v station."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataGrandLyonCoordinator,
        subentry: ConfigSubentry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._subentry_id = subentry.subentry_id
        assert subentry.unique_id is not None

        self._attr_unique_id = f"{subentry.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.unique_id)},
            name=subentry.title,
            manufacturer="JCDecaux",
            model="Station",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return True if the station data is available."""
        return (
            super().available
            and self._subentry_id in self.coordinator.data.velov_stations
        )

    @property
    def is_on(self) -> bool:
        """Return true if the station is open."""
        return (
            self.coordinator.data.velov_stations[self._subentry_id].status
            == VelovStationStatus.OPEN
        )
