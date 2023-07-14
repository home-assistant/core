"""Support for Netgear LTE binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_BINARY_SENSOR, DOMAIN
from .entity import LTEEntity
from .sensor_types import BINARY_SENSOR_CLASSES


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Netgear LTE binary sensor devices."""
    if discovery_info is None:
        return

    modem_data = hass.data[DOMAIN].get_modem_data(discovery_info)

    if not modem_data or not modem_data.data:
        raise PlatformNotReady

    binary_sensor_conf = discovery_info[CONF_BINARY_SENSOR]
    monitored_conditions = binary_sensor_conf[CONF_MONITORED_CONDITIONS]

    binary_sensors = []
    for sensor_type in monitored_conditions:
        binary_sensors.append(LTEBinarySensor(modem_data, sensor_type))

    async_add_entities(binary_sensors)


class LTEBinarySensor(LTEEntity, BinarySensorEntity):
    """Netgear LTE binary sensor entity."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self.modem_data.data, self.sensor_type)

    @property
    def device_class(self):
        """Return the class of binary sensor."""
        return BINARY_SENSOR_CLASSES[self.sensor_type]
