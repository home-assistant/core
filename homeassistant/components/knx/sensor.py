"""Support for KNX/IP sensors."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

from xknx.devices import Sensor as XknxSensor

from homeassistant.components.sensor import DEVICE_CLASSES, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import dt

from .const import ATTR_LAST_KNX_UPDATE, ATTR_SOURCE, DOMAIN
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
        self._unique_id = f"{self._device.sensor_value.group_address_state}"

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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        attr: dict[str, Any] = {}

        if self._device.last_telegram is not None:
            attr[ATTR_SOURCE] = str(self._device.last_telegram.source_address)
            attr[ATTR_LAST_KNX_UPDATE] = str(
                dt.as_utc(self._device.last_telegram.timestamp)
            )
        return attr

    @property
    def force_update(self) -> bool:
        """
        Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return self._device.always_callback
