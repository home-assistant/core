"""Support for LightwaveRF TRV - Associated Battery."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_SERIAL, LIGHTWAVE_LINK


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Find and return battery."""
    if discovery_info is None:
        return

    batteries = []

    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_config in discovery_info.values():
        name = device_config[CONF_NAME]
        serial = device_config[CONF_SERIAL]
        batteries.append(LightwaveBattery(name, lwlink, serial))

    async_add_entities(batteries)


class LightwaveBattery(SensorEntity):
    """Lightwave TRV Battery."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, name, lwlink, serial):
        """Initialize the Lightwave Trv battery sensor."""
        self._attr_name = name
        self._lwlink = lwlink
        self._serial = serial
        self._attr_unique_id = f"{serial}-trv-battery"

    def update(self):
        """Communicate with a Lightwave RTF Proxy to get state."""
        (dummy_temp, dummy_targ, battery, dummy_output) = self._lwlink.read_trv_status(
            self._serial
        )
        self._attr_native_value = battery
