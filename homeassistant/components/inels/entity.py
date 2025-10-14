"""Base class for iNELS components."""

from __future__ import annotations

from inelsmqtt.devices import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class InelsBaseEntity(Entity):
    """Base iNELS entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: Device,
        key: str,
        index: int,
    ) -> None:
        """Init base entity."""
        self._device = device
        self._device_id = device.unique_id
        self._attr_unique_id = self._device_id

        # The referenced variable to read from
        self._key = key
        # The index of the variable list to read from. '-1' for no index
        self._index = index

        info = device.info()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            manufacturer=info.manufacturer,
            model=info.model_number,
            name=device.title,
            sw_version=info.sw_version,
        )

    async def async_added_to_hass(self) -> None:
        """Add subscription of the data listener."""
        # Register the HA callback
        self._device.add_ha_callback(self._key, self._index, self._callback)
        # Subscribe to MQTT updates
        self._device.mqtt.subscribe_listener(
            self._device.state_topic, self._device.unique_id, self._device.callback
        )

    def _callback(self) -> None:
        """Get data from broker into the HA."""
        if hasattr(self, "hass"):
            self.schedule_update_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self._device.is_available)
