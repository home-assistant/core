"""Base class for deCONZ devices."""

from __future__ import annotations

from pydeconz.group import Group as DeconzGroup, Scene as PydeconzScene
from pydeconz.light import DeconzLight
from pydeconz.sensor import DeconzSensor

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN as DECONZ_DOMAIN
from .gateway import DeconzGateway


class DeconzBase:
    """Common base for deconz entities and events."""

    def __init__(
        self,
        device: DeconzGroup | DeconzLight | DeconzSensor,
        gateway: DeconzGateway,
    ) -> None:
        """Set up device and add update callback to get data from websocket."""
        self._device = device
        self.gateway = gateway

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self._device.unique_id

    @property
    def serial(self) -> str | None:
        """Return a serial number for this device."""
        if not self._device.unique_id or self._device.unique_id.count(":") != 7:
            return None

        return self._device.unique_id.split("-", 1)[0]

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        if self.serial is None:
            return None

        return DeviceInfo(
            connections={(CONNECTION_ZIGBEE, self.serial)},
            identifiers={(DECONZ_DOMAIN, self.serial)},
            manufacturer=self._device.manufacturer,
            model=self._device.model_id,
            name=self._device.name,
            sw_version=self._device.software_version,
            via_device=(DECONZ_DOMAIN, self.gateway.api.config.bridge_id),
        )


class DeconzDevice(DeconzBase, Entity):
    """Representation of a deCONZ device."""

    _attr_should_poll = False

    TYPE = ""

    def __init__(
        self,
        device: DeconzGroup | DeconzLight | DeconzSensor,
        gateway: DeconzGateway,
    ) -> None:
        """Set up device and add update callback to get data from websocket."""
        super().__init__(device, gateway)
        self.gateway.entities[self.TYPE].add(self.unique_id)

        self._attr_name = self._device.name

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events."""
        self._device.register_callback(self.async_update_callback)
        self.gateway.deconz_ids[self.entity_id] = self._device.deconz_id
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.gateway.signal_reachable,
                self.async_update_connection_state,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.remove_callback(self.async_update_callback)
        del self.gateway.deconz_ids[self.entity_id]
        self.gateway.entities[self.TYPE].remove(self.unique_id)

    @callback
    def async_update_connection_state(self) -> None:
        """Update the device's available state."""
        self.async_write_ha_state()

    @callback
    def async_update_callback(self) -> None:
        """Update the device's state."""
        if self.gateway.ignore_state_updates:
            return

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.gateway.available and self._device.reachable


class DeconzSceneMixin(DeconzDevice):
    """Representation of a deCONZ scene."""

    _device: PydeconzScene

    def __init__(self, device: PydeconzScene, gateway: DeconzGateway) -> None:
        """Set up a scene."""
        super().__init__(device, gateway)

        self._attr_name = device.full_name
        self._group_identifier = self.get_parent_identifier()

    def get_device_identifier(self) -> str:
        """Describe a unique identifier for this scene."""
        return f"{self.gateway.bridgeid}{self._device.deconz_id}"

    def get_parent_identifier(self) -> str:
        """Describe a unique identifier for group this scene belongs to."""
        return f"{self.gateway.bridgeid}-{self._device.group_deconz_id}"

    @property
    def available(self) -> bool:
        """Return True if scene is available."""
        return self.gateway.available

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this scene."""
        return self.get_device_identifier()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(identifiers={(DECONZ_DOMAIN, self._group_identifier)})
