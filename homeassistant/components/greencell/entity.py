"""Base entity for the Greencell EVSE integration."""

from typing import override

from greencell_client.access import GreencellAccess
from greencell_client.utils import GreencellUtils

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
    GREENCELL_HABU_DEN,
    GREENCELL_OTHER_DEVICE,
    MANUFACTURER,
    SIGNAL_ACCESS_CHANGED,
)


class GreencellEntity(Entity):
    """Base class for Greencell entities."""

    _attr_has_entity_name = True

    def __init__(self, serial_number: str, access: GreencellAccess) -> None:
        """Initialize the entity."""
        self._serial_number = serial_number
        self._access = access

        if GreencellUtils.device_is_habu_den(serial_number):
            device_name = GREENCELL_HABU_DEN
        else:
            device_name = GREENCELL_OTHER_DEVICE

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"{device_name} {serial_number}",
            manufacturer=MANUFACTURER,
            model=device_name,
            serial_number=serial_number,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the entity is available."""
        return super().available and not self._access.is_disabled()

    @override
    async def async_added_to_hass(self) -> None:
        """Register the entity with Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ACCESS_CHANGED.format(self._serial_number),
                self.async_write_ha_state,
            )
        )
