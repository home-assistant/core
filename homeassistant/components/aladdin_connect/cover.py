"""Cover Entity for Genie Garage Door."""

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AladdinConnectConfigEntry, AladdinConnectCoordinator
from .const import DOMAIN
from .entity import AladdinConnectEntity
from .model import GarageDoor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AladdinConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aladdin Connect platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(AladdinDevice(coordinator, door) for door in coordinator.doors)
    remove_stale_devices(hass, config_entry)


def remove_stale_devices(
    hass: HomeAssistant, config_entry: AladdinConnectConfigEntry
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = {door.unique_id for door in config_entry.runtime_data.doors}

    for device_entry in device_entries:
        device_id: str | None = None

        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                break

        if device_id is None or device_id not in all_device_ids:
            # If device_id is None an invalid device entry was found for this config entry.
            # If the device_id is not in existing device ids it's a stale device entry.
            # Remove config entry from this device entry in either case.
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )


class AladdinDevice(AladdinConnectEntity, CoverEntity):
    """Representation of Aladdin Connect cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    def __init__(
        self, coordinator: AladdinConnectCoordinator, device: GarageDoor
    ) -> None:
        """Initialize the Aladdin Connect cover."""
        super().__init__(coordinator, device)
        self._attr_unique_id = device.unique_id

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        await self.coordinator.acc.open_door(
            self._device.device_id, self._device.door_number
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        await self.coordinator.acc.close_door(
            self._device.device_id, self._device.door_number
        )

    @property
    def is_closed(self) -> bool | None:
        """Update is closed attribute."""
        value = self.coordinator.acc.get_door_status(
            self._device.device_id, self._device.door_number
        )
        if value is None:
            return None
        return bool(value == "closed")

    @property
    def is_closing(self) -> bool | None:
        """Update is closing attribute."""
        value = self.coordinator.acc.get_door_status(
            self._device.device_id, self._device.door_number
        )
        if value is None:
            return None
        return bool(value == "closing")

    @property
    def is_opening(self) -> bool | None:
        """Update is opening attribute."""
        value = self.coordinator.acc.get_door_status(
            self._device.device_id, self._device.door_number
        )
        if value is None:
            return None
        return bool(value == "opening")
