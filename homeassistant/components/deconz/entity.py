"""Base class for deCONZ devices."""

from __future__ import annotations

from pydeconz.models.deconz_device import DeconzDevice as PydeconzDevice
from pydeconz.models.group import Group as PydeconzGroup
from pydeconz.models.light import LightBase as PydeconzLightBase
from pydeconz.models.scene import Scene as PydeconzScene
from pydeconz.models.sensor import SensorBase as PydeconzSensorBase

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import DeconzHub
from .util import serial_from_unique_id

type _DeviceType = (
    PydeconzGroup | PydeconzLightBase | PydeconzSensorBase | PydeconzScene
)


class DeconzBase[_DeviceT: _DeviceType]:
    """Common base for deconz entities and events."""

    unique_id_suffix: str | None = None

    def __init__(
        self,
        device: _DeviceT,
        hub: DeconzHub,
    ) -> None:
        """Set up device and add update callback to get data from websocket."""
        self._device: _DeviceT = device
        self.hub = hub

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        assert isinstance(self._device, PydeconzDevice)
        if self.unique_id_suffix is not None:
            return f"{self._device.unique_id}-{self.unique_id_suffix}"
        return self._device.unique_id

    @property
    def serial(self) -> str | None:
        """Return a serial number for this device."""
        assert isinstance(self._device, PydeconzDevice)
        return serial_from_unique_id(self._device.unique_id)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        assert isinstance(self._device, PydeconzDevice)
        if self.serial is None:
            return None

        return DeviceInfo(
            connections={(CONNECTION_ZIGBEE, self.serial)},
            identifiers={(DOMAIN, self.serial)},
            manufacturer=self._device.manufacturer,
            model=self._device.model_id,
            name=self._device.name,
            sw_version=self._device.software_version,
            via_device=(DOMAIN, self.hub.api.config.bridge_id),
        )


class DeconzDevice[_DeviceT: _DeviceType](DeconzBase[_DeviceT], Entity):
    """Representation of a deCONZ device."""

    _attr_should_poll = False

    _name_suffix: str | None = None
    _update_key: str | None = None
    _update_keys: set[str] | None = None

    TYPE = ""

    def __init__(
        self,
        device: _DeviceT,
        hub: DeconzHub,
    ) -> None:
        """Set up device and add update callback to get data from websocket."""
        super().__init__(device, hub)
        self.hub.entities[self.TYPE].add(self.unique_id)

        self._attr_name = self._device.name
        if self._name_suffix is not None:
            self._attr_name += f" {self._name_suffix}"

        if self._update_key is not None:
            self._update_keys = {self._update_key}
        if self._update_keys is not None:
            self._update_keys |= {"reachable"}

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events."""
        self._device.register_callback(self.async_update_callback)
        self.hub.deconz_ids[self.entity_id] = self._device.deconz_id
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.hub.signal_reachable,
                self.async_update_connection_state,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.remove_callback(self.async_update_callback)
        del self.hub.deconz_ids[self.entity_id]
        self.hub.entities[self.TYPE].remove(self.unique_id)

    @callback
    def async_update_connection_state(self) -> None:
        """Update the device's available state."""
        self.async_write_ha_state()

    @callback
    def async_update_callback(self) -> None:
        """Update the device's state."""
        if self.hub.ignore_state_updates:
            return

        if self._update_keys is not None and not self._device.changed_keys.intersection(
            self._update_keys
        ):
            return

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        if isinstance(self._device, PydeconzScene):
            return self.hub.available
        return self.hub.available and self._device.reachable


class DeconzSceneMixin(DeconzDevice[PydeconzScene]):
    """Representation of a deCONZ scene."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: PydeconzScene,
        hub: DeconzHub,
    ) -> None:
        """Set up a scene."""
        super().__init__(device, hub)

        self.group = self.hub.api.groups[device.group_id]

        self._attr_name = device.name
        self._group_identifier = self.get_parent_identifier()

    def get_device_identifier(self) -> str:
        """Describe a unique identifier for this scene."""
        return f"{self.hub.bridgeid}{self._device.deconz_id}"

    def get_parent_identifier(self) -> str:
        """Describe a unique identifier for group this scene belongs to."""
        return f"{self.hub.bridgeid}-{self.group.deconz_id}"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this scene."""
        return self.get_device_identifier()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._group_identifier)},
            manufacturer="Dresden Elektronik",
            model="deCONZ group",
            name=self.group.name,
            via_device=(DOMAIN, self.hub.api.config.bridge_id),
        )
