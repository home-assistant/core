"""Provide a common entity class for myUplink entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyUplinkDataCoordinator


class MyUplinkEntity(CoordinatorEntity[MyUplinkDataCoordinator]):
    """Representation of myuplink entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator)

        # Internal properties
        self.device_id = device_id

        # Basic values
        self._attr_unique_id = f"{device_id}-{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})


class MyUplinkSystemEntity(MyUplinkEntity):
    """Representation of a system bound entity."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        system_id: str,
        device_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.system_id = system_id

        # Basic values
        self._attr_unique_id = f"{system_id}-{unique_id_suffix}"
