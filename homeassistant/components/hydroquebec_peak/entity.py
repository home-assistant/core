"""Base entity for the Hydro-Québec Peak Events integration."""

from urllib.parse import quote

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENTS_TABLE_URL
from .coordinator import HydroQuebecPeakCoordinator


class HydroQuebecPeakEntity(CoordinatorEntity[HydroQuebecPeakCoordinator]):
    """Base entity: one device per configured offer."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HydroQuebecPeakCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.offer}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.offer)},
            name=coordinator.offer,
            manufacturer="Hydro-Québec",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=(
                f"{EVENTS_TABLE_URL}&refine.offre={quote(coordinator.offer)}"
            ),
        )
