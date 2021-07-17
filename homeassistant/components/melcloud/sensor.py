"""Support for MelCloud device sensors."""
from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW
from pymelcloud.atw_device import Zone

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ENERGY_KILO_WATT_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.util import dt as dt_util

from . import MelCloudDevice
from .const import DOMAIN

ATTR_MEASUREMENT_NAME = "measurement_name"
ATTR_UNIT = "unit"
ATTR_VALUE_FN = "value_fn"
ATTR_ENABLED_FN = "enabled"

ATA_SENSORS = {
    "room_temperature": {
        ATTR_MEASUREMENT_NAME: "Room Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda x: x.device.room_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "energy": {
        ATTR_MEASUREMENT_NAME: "Energy",
        ATTR_ICON: "mdi:factory",
        ATTR_UNIT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        ATTR_VALUE_FN: lambda x: x.device.total_energy_consumed,
        ATTR_ENABLED_FN: lambda x: x.device.has_energy_consumed_meter,
    },
}
ATW_SENSORS = {
    "outside_temperature": {
        ATTR_MEASUREMENT_NAME: "Outside Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda x: x.device.outside_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "tank_temperature": {
        ATTR_MEASUREMENT_NAME: "Tank Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda x: x.device.tank_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
}
ATW_ZONE_SENSORS = {
    "room_temperature": {
        ATTR_MEASUREMENT_NAME: "Room Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda zone: zone.room_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "flow_temperature": {
        ATTR_MEASUREMENT_NAME: "Flow Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda zone: zone.flow_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
    "return_temperature": {
        ATTR_MEASUREMENT_NAME: "Flow Return Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_VALUE_FN: lambda zone: zone.return_temperature,
        ATTR_ENABLED_FN: lambda x: True,
    },
}


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


class MelDeviceSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: MelCloudDevice, measurement, definition):
        """Initialize the sensor."""
        self._api = api
        self._def = definition

        self._attr_device_class = definition[ATTR_DEVICE_CLASS]
        self._attr_icon = definition[ATTR_ICON]
        self._attr_name = f"{api.name} {definition[ATTR_MEASUREMENT_NAME]}"
        self._attr_unique_id = f"{api.device.serial}-{api.device.mac}-{measurement}"
        self._attr_unit_of_measurement = definition[ATTR_UNIT]
        self._attr_state_class = STATE_CLASS_MEASUREMENT

        if self.device_class == DEVICE_CLASS_ENERGY:
            self._attr_last_reset = dt_util.utc_from_timestamp(0)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._def[ATTR_VALUE_FN](self._api)

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
        if zone.zone_index == 1:
            full_measurement = measurement
        else:
            full_measurement = f"{measurement}-zone-{zone.zone_index}"
        super().__init__(api, full_measurement, definition)
        self._zone = zone
        self._attr_name = f"{api.name} {zone.name} {definition[ATTR_MEASUREMENT_NAME]}"

    @property
    def state(self):
        """Return zone based state."""
        return self._def[ATTR_VALUE_FN](self._zone)
