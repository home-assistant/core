"""SimpleFin Base Entity."""
from simplefin4py import Account

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SimpleFinDataUpdateCoordinator


class SimpleFinEntity(CoordinatorEntity[SimpleFinDataUpdateCoordinator]):
    """Define a generic class for SimpleFIN entities."""

    _attr_attribution = "Data provided by SimpleFIN API"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SimpleFinDataUpdateCoordinator,
        description: EntityDescription,
        account: Account,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._account_id = account.id

        self._attr_unique_id = f"account_{account.id}_{description.key}".lower()
        self._attr_name = f"{account.name} {description.translation_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account.org.domain)},
            name=account.org.name,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="SimpleFIN",
            model="Account",
        )
