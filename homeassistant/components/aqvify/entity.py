"""Defines a base Aqvify entity."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AqvifyAggrDataCoordinator, AqvifyCoordinator


class AqvifyBaseEntity[
    _AqvifyCoordinatorT: AqvifyCoordinator | AqvifyAggrDataCoordinator
](CoordinatorEntity[_AqvifyCoordinatorT]):
    """Defines a base Aqvify entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _AqvifyCoordinatorT,
        device_key: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the Aqvify entity."""
        super().__init__(coordinator)

        self.account_id = self.coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert self.account_id is not None

        self.device_key = device_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.account_id}_{device_key}")},
        )
        self.entity_description = description
        self._attr_unique_id = f"{self.account_id}_{device_key}_{description.key}"


class AqvifyEntity(AqvifyBaseEntity[AqvifyCoordinator]):
    """Base class for Aqvify entities that use main data coordinator."""

    def __init__(
        self,
        coordinator: AqvifyCoordinator,
        device_key: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator, device_key, description)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.account_id}_{device_key}")},
            name=coordinator.data.devices.devices[device_key].name,
            manufacturer="Aqvify",
            configuration_url="https://app.aqvify.com",
            serial_number=device_key,
        )


class AqvifyAggrEntity(AqvifyBaseEntity[AqvifyAggrDataCoordinator]):
    """Defines a base Aqvify entity for aggregated data."""
