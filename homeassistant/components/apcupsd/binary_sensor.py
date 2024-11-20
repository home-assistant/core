"""Support for tracking the online status of a UPS."""

from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import APCUPSdConfigEntry
from .coordinator import APCUPSdCoordinator

PARALLEL_UPDATES = 0

_DESCRIPTION = BinarySensorEntityDescription(
    key="statflag",
    translation_key="online_status",
)
# The bit in STATFLAG that indicates the online status of the APC UPS.
_VALUE_ONLINE_MASK: Final = 0b1000


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: APCUPSdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an APCUPSd Online Status binary sensor."""
    coordinator = config_entry.runtime_data

    # Do not create the binary sensor if APCUPSd does not provide STATFLAG field for us
    # to determine the online status.
    if _DESCRIPTION.key.upper() not in coordinator.data:
        return

    async_add_entities([OnlineStatus(coordinator, _DESCRIPTION)])


class OnlineStatus(CoordinatorEntity[APCUPSdCoordinator], BinarySensorEntity):
    """Representation of a UPS online status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: APCUPSdCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the APCUPSd binary device."""
        super().__init__(coordinator, context=description.key.upper())

        # Set up unique id and device info if serial number is available.
        if (serial_no := coordinator.data.serial_no) is not None:
            self._attr_unique_id = f"{serial_no}_{description.key}"
        self.entity_description = description
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Returns true if the UPS is online."""
        # Check if ONLINE bit is set in STATFLAG.
        key = self.entity_description.key.upper()
        # The daemon could either report just a hex ("0x05000008"), or a hex with a "Status Flag"
        # suffix ("0x05000008 Status Flag") in older versions.
        # Here we trim the suffix if it exists to support both.
        flag = self.coordinator.data[key].removesuffix(" Status Flag")
        return int(flag, 16) & _VALUE_ONLINE_MASK != 0
