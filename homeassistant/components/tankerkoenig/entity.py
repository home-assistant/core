"""The tankerkoenig base entity."""
from aiotankerkoenig import Station

from homeassistant.const import ATTR_ID
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TankerkoenigDataUpdateCoordinator


class TankerkoenigCoordinatorEntity(
    CoordinatorEntity[TankerkoenigDataUpdateCoordinator]
):
    """Tankerkoenig base entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TankerkoenigDataUpdateCoordinator, station: Station
    ) -> None:
        """Initialize the Tankerkoenig base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(ATTR_ID, station.id)},
            name=f"{station.brand} {station.street} {station.house_number}",
            model=station.brand,
            configuration_url="https://www.tankerkoenig.de",
            entry_type=DeviceEntryType.SERVICE,
        )
