"""Home Connect entity base class."""

from abc import abstractmethod
import logging

from aiohomeconnect.model import Event, EventKey, HomeAppliance

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectCoordinator

_LOGGER = logging.getLogger(__name__)


class HomeConnectEntity(Entity):
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
        self.coordinator = coordinator
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

    async def async_added_to_hass(self) -> None:
        """Register listener."""
        await super().async_added_to_hass()
        self.coordinator.add_home_appliances_event_listener(
            self.appliance.info.ha_id,
            EventKey(self.bsh_key),
            self._async_event_update_listener,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister listener."""
        await super().async_will_remove_from_hass()
        self.coordinator.delete_home_appliances_event_listener(
            self.appliance.info.ha_id,
            EventKey(self.bsh_key),
            self._async_event_update_listener,
        )

    @abstractmethod
    async def _async_event_update_listener(self, event: Event) -> None:
        """Update status when an event for the entity is received."""

    @property
    def bsh_key(self) -> str:
        """Return the BSH key."""
        return self.entity_description.key
