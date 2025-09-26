"""Support for ZoneMinder binary sensors."""

from __future__ import annotations

from zoneminder.zm import ZoneMinder

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZoneMinder binary sensor platform."""
    sensors = []
    for host_name, zm_client in hass.data[DOMAIN].items():
        sensors.append(ZMAvailabilitySensor(host_name, zm_client))
    add_entities(sensors)


class ZMAvailabilitySensor(BinarySensorEntity):
    """Representation of the availability of ZoneMinder as a binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, host_name: str, client: ZoneMinder) -> None:
        """Initialize availability sensor."""
        self._attr_name = host_name
        self._client = client

    def update(self) -> None:
        """Update the state of this sensor (availability of ZoneMinder)."""
        self._attr_is_on = self._client.is_available
