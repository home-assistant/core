"""The mapping of a CCL Entity."""

from __future__ import annotations

from aioccl import CCLDevice, CCLSensor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class CCLEntity(Entity):
    """Representation of a CCL Entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        internal: CCLSensor,
        device: CCLDevice,
    ) -> None:
        """Initialize a CCL Entity."""
        self._internal = internal
        self._device = device

        self._attr_unique_id = f"{device.device_id}-{internal.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.device_id),
            },
            name=self.device_name,
            model=device.model,
            manufacturer="CCL Electronics",
            sw_version=device.fw_ver,
        )

    @property
    def device_name(self) -> str:
        """Return the device name."""
        if self._internal.compartment is not None:
            return self._device.name + " " + self._internal.compartment
        return self._device.name

    @property
    def device_id(self) -> str:
        """Return the 6-digits device id."""
        if self._internal.compartment is not None:
            return (
                (self.device_name + "_" + self._internal.compartment)
                .replace(" ", "")
                .replace("-", "_")
                .lower()
            )
        return self.device_name.replace(" ", "").replace("-", "_").lower()

    @property
    def available(self) -> bool:
        """Return the availability."""
        return self._internal.value is not None

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._device.register_update_cb(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._device.remove_update_cb(self.async_write_ha_state)
