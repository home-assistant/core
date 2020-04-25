"""Support for MelCloud device sensors."""
import logging

from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW
from pymelcloud.atw_device import Zone

from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity

from . import MelCloudDevice
from .const import DOMAIN, TEMP_UNIT_LOOKUP

ATTR_MEASUREMENT_NAME = "measurement_name"
ATTR_ICON = "icon"
ATTR_UNIT_FN = "unit_fn"
ATTR_DEVICE_CLASS = "device_class"
ATTR_VALUE_FN = "value_fn"
ATTR_ENABLED_FN = "enabled"

ATA_SENSORS = {
    "room_temperature": {
        ATTR_MEASUREMENT_NAME: "Room Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_FN: lambda x: TEMP_UNIT_LOOKUP.get(x.device.temp_unit, TEMP_CELSIUS),
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda x: x.device.room_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "energy": {
        ATTR_MEASUREMENT_NAME: "Energy",
        ATTR_ICON: "mdi:factory",
        ATTR_UNIT_FN: lambda x: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_VALUE_FN: lambda x: x.device.total_energy_consumed,
        ATTR_ENABLED_FN: lambda x: x.device.has_energy_consumed_meter,
    },
}
ATW_SENSORS = {
    "outside_temperature": {
        ATTR_MEASUREMENT_NAME: "Outside Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_FN: lambda x: TEMP_UNIT_LOOKUP.get(x.device.temp_unit, TEMP_CELSIUS),
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda x: x.device.outside_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "tank_temperature": {
        ATTR_MEASUREMENT_NAME: "Tank Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_FN: lambda x: TEMP_UNIT_LOOKUP.get(x.device.temp_unit, TEMP_CELSIUS),
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda x: x.device.tank_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
}
ATW_ZONE_SENSORS = {
    "room_temperature": {
        ATTR_MEASUREMENT_NAME: "Room Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_FN: lambda x: TEMP_UNIT_LOOKUP.get(x.device.temp_unit, TEMP_CELSIUS),
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda zone: zone.room_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "flow_temperature": {
        ATTR_MEASUREMENT_NAME: "Flow Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_FN: lambda x: TEMP_UNIT_LOOKUP.get(x.device.temp_unit, TEMP_CELSIUS),
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda zone: zone.flow_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "return_temperature": {
        ATTR_MEASUREMENT_NAME: "Flow Return Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_FN: lambda x: TEMP_UNIT_LOOKUP.get(x.device.temp_unit, TEMP_CELSIUS),
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda zone: zone.return_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MELCloud device sensors based on config_entry."""
    mel_devices = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities(
        [
            MelDeviceSensor(mel_device, measurement, definition)
            for measurement, definition in ATA_SENSORS.items()
            for mel_device in mel_devices[DEVICE_TYPE_ATA]
            if definition[ATTR_ENABLED_FN](mel_device)
        ]
        + [
            MelDeviceSensor(mel_device, measurement, definition)
            for measurement, definition in ATW_SENSORS.items()
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
            if definition[ATTR_ENABLED_FN](mel_device)
        ]
        + [
            AtwZoneSensor(mel_device, zone, measurement, definition)
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
            for zone in mel_device.device.zones
            for measurement, definition, in ATW_ZONE_SENSORS.items()
            if definition[ATTR_ENABLED_FN](zone)
        ],
        True,
    )


class MelDeviceSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, api: MelCloudDevice, measurement, definition):
        """Initialize the sensor."""
        self._api = api
        self._name_slug = api.name
        self._measurement = measurement
        self._def = definition

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.device.serial}-{self._api.device.mac}-{self._measurement}"

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._def[ATTR_ICON]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name_slug} {self._def[ATTR_MEASUREMENT_NAME]}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._def[ATTR_VALUE_FN](self._api)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._def[ATTR_UNIT_FN](self._api)

    @property
    def device_class(self):
        """Return device class."""
        return self._def[ATTR_DEVICE_CLASS]

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info


class AtwZoneSensor(MelDeviceSensor):
    """Air-to-Air device sensor."""

    def __init__(self, api: MelCloudDevice, zone: Zone, measurement, definition):
        """Initialize the sensor."""
        super().__init__(api, measurement, definition)
        self._zone = zone
        self._name_slug = f"{api.name} {zone.name}"

    @property
    def state(self):
        """Return zone based state."""
        return self._def[ATTR_VALUE_FN](self._zone)
