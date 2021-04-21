"""Support for KNX/IP binary sensors."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

from xknx.devices import BinarySensor as XknxBinarySensor

from homeassistant.components.binary_sensor import DEVICE_CLASSES, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt

from .const import ATTR_COUNTER, ATTR_LAST_KNX_UPDATE, ATTR_SOURCE, DOMAIN
from .knx_entity import KnxEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[Iterable[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up binary sensor(s) for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxBinarySensor):
            entities.append(KNXBinarySensor(device))
    async_add_entities(entities)


class KNXBinarySensor(KnxEntity, BinarySensorEntity):
    """Representation of a KNX binary sensor."""

    def __init__(self, device: XknxBinarySensor) -> None:
        """Initialize of KNX binary sensor."""
        self._device: XknxBinarySensor
        super().__init__(device)

    @property
    def device_class(self) -> str | None:
        """Return the class of this sensor."""
        if self._device.device_class in DEVICE_CLASSES:
            return self._device.device_class
        return None

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._device.is_on()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        attr: dict[str, Any] = {}

        if self._device.counter is not None:
            attr[ATTR_COUNTER] = self._device.counter
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
        return self._device.ignore_internal_state
