"""Home Connect entity base class."""

from abc import abstractmethod

from aiohomeconnect.model import EventKey, HomeAppliance

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectCoordinator


class HomeConnectEntity(CoordinatorEntity[HomeConnectCoordinator]):
    """Generic Home Connect entity (base class)."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    @staticmethod
    def create_unique_id(appliance: HomeAppliance, key: str) -> str:
        """Create unique id for entity."""
        return f"{appliance.ha_id}-{key}"

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, (appliance.info.ha_id, EventKey(desc.key)))
        self.appliance = appliance
        self.entity_description = desc
        self._attr_unique_id = HomeConnectEntity.create_unique_id(
            appliance.info, desc.key
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance.info.ha_id)},
            manufacturer=appliance.info.brand,
            model=appliance.info.vib,
            name=appliance.info.name,
        )
        self.update_native_value()

    @abstractmethod
    def update_native_value(self) -> None:
        """Set the value of the entity."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_native_value()
        self.async_write_ha_state()

    @property
    def bsh_key(self) -> str:
        """Return the BSH key."""
        return self.entity_description.key
