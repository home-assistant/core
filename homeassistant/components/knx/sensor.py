"""Support for KNX/IP sensors."""
from __future__ import annotations

from typing import Callable, Iterable

from xknx.devices import Sensor as XknxSensor

from homeassistant.components.sensor import DEVICE_CLASSES, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import DOMAIN
from .knx_entity import KnxEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[Iterable[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up sensor(s) for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxSensor):
            entities.append(KNXSensor(device))
    async_add_entities(entities)


class KNXSensor(KnxEntity, SensorEntity):
    """Representation of a KNX sensor."""

    def __init__(self, device: XknxSensor) -> None:
        """Initialize of a KNX sensor."""
        self._device: XknxSensor
        super().__init__(device)

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.resolve_state()

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return self._device.unit_of_measurement()

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        device_class = self._device.ha_device_class()
        if device_class in DEVICE_CLASSES:
            return device_class
        return None

    @property
    def force_update(self) -> bool:
        """
        Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return self._device.always_callback
