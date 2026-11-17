"""Base entity for the ecosmart integration."""

from aioecosmart import IcpScope, Spot

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONFIGURATION_URL, DOMAIN, MANUFACTURER
from .coordinator import EcosmartCoordinator


class EcosmartEntity(CoordinatorEntity[EcosmartCoordinator]):
    """An entity describing prices at one connection point.

    Each ICP -- the fifteen-character Installation Control Point number that
    identifies a New Zealand electricity connection -- gets its own service
    device, so a customer with several properties can tell them apart.
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcosmartCoordinator,
        icp: IcpScope,
        description: EntityDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.icp = icp
        self._attr_unique_id = f"{icp.icp}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, icp.icp)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=icp.poc,
            name=icp.icp,
            configuration_url=CONFIGURATION_URL,
        )

    @property
    def spot(self) -> Spot:
        """Return this connection point's price from the last successful fetch."""
        return self.coordinator.data[self.icp.poc]
