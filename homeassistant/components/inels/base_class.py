"""Base class for iNELS components."""
from __future__ import annotations

from typing import Any

from inelsmqtt.devices import Device

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class InelsBaseEntity(Entity):
    """Base Inels device."""

    def __init__(
        self,
        device: Device,
    ) -> None:
        """Init base entity."""
        self._device: Device = device
        self._device_id = self._device.unique_id
        self._attr_name = self._device.title

        self._parent_id = self._device.parent_id
        self._attr_unique_id = f"{self._parent_id}-{self._device_id}"

    async def async_added_to_hass(self) -> None:
        """Add subscription of the data listenere."""
        self.async_on_remove(
            self._device.mqtt.subscribe_listener(
                self._device.state_topic, self._attr_unique_id, self._callback
            )
        )

    def _callback(self, new_value: Any) -> None:
        """Get data from broker into the HA."""
        self._device.update_value(new_value)
        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        info = self._device.info()
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.unique_id)},
            manufacturer=info.manufacturer,
            model=info.model_number,
            name=self._device.title,
            sw_version=info.sw_version,
            via_device=(DOMAIN, self._parent_id),
        )

    @property
    def available(self) -> bool:
        """Return if entity si available."""
        if self._device.is_subscribed is False:
            self._device.mqtt.subscribe(self._device.state_topic)

        return self._device.is_available and super().available
