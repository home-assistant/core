"""Base class shared among IRM KMI entities."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, IRM_KMI_NAME
from .coordinator import IrmKmiConfigEntry, IrmKmiCoordinator
from .utils import preferred_language


class IrmKmiBaseEntity(CoordinatorEntity[IrmKmiCoordinator]):
    """Base methods for IRM KMI entities."""

    _attr_attribution = (
        "Weather data from the Royal Meteorological Institute of Belgium meteo.be"
    )
    _attr_has_entity_name = True

    def __init__(self, entry: IrmKmiConfigEntry) -> None:
        """Init base properties for IRM KMI entities."""
        coordinator = entry.runtime_data
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=IRM_KMI_NAME.get(preferred_language(self.hass, entry)),
        )
