"""Home Connect entity base class."""

from abc import abstractmethod
import logging

from aiohomeconnect.model import EventKey

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectCoordinator

_LOGGER = logging.getLogger(__name__)


class HomeConnectEntity(CoordinatorEntity[HomeConnectCoordinator]):
    """Generic Home Connect entity (base class)."""

    _attr_should_poll = False
    _attr_has_entity_name = True

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
        self._attr_unique_id = f"{appliance.info.ha_id}-{desc.key}"
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
        _LOGGER.debug("Updated %s, new state: %s", self.entity_id, self.state)

    @property
    def bsh_key(self) -> str:
        """Return the BSH key."""
        return self.entity_description.key

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.appliance.info.connected and self._attr_available and super().available
        )
