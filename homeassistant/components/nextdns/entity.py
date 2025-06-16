"""Define NextDNS entities."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CoordinatorDataT, NextDnsUpdateCoordinator


class NextDnsEntity(CoordinatorEntity[NextDnsUpdateCoordinator[CoordinatorDataT]]):
    """Define NextDNS entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextDnsUpdateCoordinator[CoordinatorDataT],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
