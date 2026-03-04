"""The AuroraWatch component."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AurowatchDataUpdateCoordinator


class AurowatchEntity(CoordinatorEntity[AurowatchDataUpdateCoordinator]):
    """Implementation of the base AuroraWatch Entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AurowatchDataUpdateCoordinator,
        translation_key: str,
    ) -> None:
        """Initialize the AuroraWatch Entity."""

        super().__init__(coordinator=coordinator)

        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{translation_key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, DOMAIN)},
            manufacturer="Lancaster University",
            model="AuroraWatch UK",
            name="AuroraWatch UK",
        )
