"""Support for MelCloud device sensors."""
from __future__ import annotations

from typing import Any, Callable, NamedTuple

from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW
from pymelcloud.atw_device import Zone

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, TEMP_CELSIUS
from homeassistant.util import dt as dt_util

from . import MelCloudDevice
from .const import DOMAIN


class SensorMetadata(NamedTuple):
    """Metadata for an individual sensor."""

    measurement_name: str
    icon: str
    unit: str
    device_class: str
    value_fn: Callable[[Any], float]
    enabled: Callable[[Any], bool]


ATA_SENSORS: dict[str, SensorMetadata] = {
    "room_temperature": SensorMetadata(
        "Room Temperature",
        icon="mdi:thermometer",
        unit=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        value_fn=lambda x: x.device.room_temperature,
        enabled=lambda x: True,
    ),
    "energy": SensorMetadata(
        "Energy",
        icon="mdi:factory",
        unit=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        value_fn=lambda x: x.device.total_energy_consumed,
        enabled=lambda x: x.device.has_energy_consumed_meter,
    ),
}
ATW_SENSORS: dict[str, SensorMetadata] = {
    "outside_temperature": SensorMetadata(
        "Outside Temperature",
        icon="mdi:thermometer",
        unit=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        value_fn=lambda x: x.device.outside_temperature,
        enabled=lambda x: True,
    ),
    "tank_temperature": SensorMetadata(
        "Tank Temperature",
        icon="mdi:thermometer",
        unit=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        value_fn=lambda x: x.device.tank_temperature,
        enabled=lambda x: True,
    ),
}
ATW_ZONE_SENSORS: dict[str, SensorMetadata] = {
    "room_temperature": SensorMetadata(
        "Room Temperature",
        icon="mdi:thermometer",
        unit=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        value_fn=lambda zone: zone.room_temperature,
        enabled=lambda x: True,
    ),
    "flow_temperature": SensorMetadata(
        "Flow Temperature",
        icon="mdi:thermometer",
        unit=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        value_fn=lambda zone: zone.flow_temperature,
        enabled=lambda x: True,
    ),
    "return_temperature": SensorMetadata(
        "Flow Return Temperature",
        icon="mdi:thermometer",
        unit=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        value_fn=lambda zone: zone.return_temperature,
        enabled=lambda x: True,
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MELCloud device sensors based on config_entry."""
    mel_devices = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities(
        [
            MelDeviceSensor(mel_device, measurement, metadata)
            for measurement, metadata in ATA_SENSORS.items()
            for mel_device in mel_devices[DEVICE_TYPE_ATA]
            if metadata.enabled(mel_device)
        ]
        + [
            MelDeviceSensor(mel_device, measurement, metadata)
            for measurement, metadata in ATW_SENSORS.items()
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
            if metadata.enabled(mel_device)
        ]
        + [
            AtwZoneSensor(mel_device, zone, measurement, metadata)
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
            for zone in mel_device.device.zones
            for measurement, metadata, in ATW_ZONE_SENSORS.items()
            if metadata.enabled(zone)
        ],
        True,
    )


class MelDeviceSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: MelCloudDevice, measurement, metadata: SensorMetadata):
        """Initialize the sensor."""
        self._api = api
        self._metadata = metadata

        self._attr_device_class = metadata.device_class
        self._attr_icon = metadata.icon
        self._attr_name = f"{api.name} {metadata.measurement_name}"
        self._attr_unique_id = f"{api.device.serial}-{api.device.mac}-{measurement}"
        self._attr_unit_of_measurement = metadata.unit
        self._attr_state_class = STATE_CLASS_MEASUREMENT

        if metadata.device_class == DEVICE_CLASS_ENERGY:
            self._attr_last_reset = dt_util.utc_from_timestamp(0)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._metadata.value_fn(self._api)

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info


class AtwZoneSensor(MelDeviceSensor):
    """Air-to-Air device sensor."""

    def __init__(
        self, api: MelCloudDevice, zone: Zone, measurement, metadata: SensorMetadata
    ):
        """Initialize the sensor."""
        if zone.zone_index == 1:
            full_measurement = measurement
        else:
            full_measurement = f"{measurement}-zone-{zone.zone_index}"
        super().__init__(api, full_measurement, metadata)
        self._zone = zone
        self._attr_name = f"{api.name} {zone.name} {metadata.measurement_name}"

    @property
    def state(self):
        """Return zone based state."""
        return self._metadata.value_fn(self._zone)
