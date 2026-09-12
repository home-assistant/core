"""Base entity for the ecosmart integration."""

from aioecosmart import IcpScope

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONFIGURATION_URL, DOMAIN, MANUFACTURER
from .coordinator import EcosmartCoordinator


class EcosmartEntity[_DataT](CoordinatorEntity[EcosmartCoordinator[_DataT]]):
    """An entity describing prices at one connection point.

    Each ICP -- the fifteen-character Installation Control Point number that
    identifies a New Zealand electricity connection -- gets its own service
    device, so a customer with several properties can tell them apart.
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcosmartCoordinator[_DataT],
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
    def _price_data(self) -> _DataT:
        """This connection point's slice of the coordinator's last fetch.

        Always present: the coordinator fetches every grid exit point named by
        the same identity the entities were built from, and a failed refresh
        keeps the previous reading rather than dropping it.
        """
        return self.coordinator.data[self.icp.poc]
