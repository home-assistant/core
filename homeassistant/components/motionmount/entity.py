"""Support for MotionMount sensors."""

import motionmount

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS, ATTR_IDENTIFIERS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, EMPTY_MAC


class MotionMountEntity(Entity):
    """Representation of a MotionMount entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, mm: motionmount.MotionMount, config_entry: ConfigEntry) -> None:
        """Initialize general MotionMount entity."""
        self.mm = mm
        mac = format_mac(mm.mac.hex())

        # Create a base unique id
        if mac == EMPTY_MAC:
            self._base_unique_id = config_entry.entry_id
        else:
            self._base_unique_id = mac

        # Set device info
        self._attr_device_info = DeviceInfo(
            name=mm.name,
            manufacturer="Vogel's",
            model="TVM 7675",
        )

        if mac == EMPTY_MAC:
            self._attr_device_info[ATTR_IDENTIFIERS] = {(DOMAIN, config_entry.entry_id)}
        else:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, mac)
            }

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self.mm.add_listener(self.async_write_ha_state)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Remove register state change callback."""
        self.mm.remove_listener(self.async_write_ha_state)
        await super().async_will_remove_from_hass()
