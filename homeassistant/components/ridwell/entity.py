"""Define a base Ridwell entity."""
from aioridwell.model import RidwellAccount, RidwellPickupEvent

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RidwellDataUpdateCoordinator


class RidwellEntity(CoordinatorEntity[RidwellDataUpdateCoordinator]):
    """Define a base Ridwell entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RidwellDataUpdateCoordinator,
        account: RidwellAccount,
        description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._account = account
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.dashboard_url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.user_id)},
            manufacturer="Ridwell",
            name="Ridwell",
        )
        self._attr_unique_id = f"{account.account_id}_{description.key}"
        self.entity_description = description

    @property
    def next_pickup_event(self) -> RidwellPickupEvent:
        """Get the next pickup event."""
        return self.coordinator.data[self._account.account_id]
