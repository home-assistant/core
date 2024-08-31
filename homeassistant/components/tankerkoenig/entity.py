"""The tankerkoenig base entity."""
from homeassistant.const import ATTR_ID
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TankerkoenigDataUpdateCoordinator


class TankerkoenigCoordinatorEntity(CoordinatorEntity):
    """Tankerkoenig base entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TankerkoenigDataUpdateCoordinator, station: dict
    ) -> None:
        """Initialize the Tankerkoenig base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(ATTR_ID, station["id"])},
            name=f"{station['brand']} {station['street']} {station['houseNumber']}",
            model=station["brand"],
            configuration_url="https://www.tankerkoenig.de",
            entry_type=DeviceEntryType.SERVICE,
        )
