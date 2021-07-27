"""Support for MelCloud device sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW
from pymelcloud.atw_device import Zone

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, TEMP_CELSIUS
from homeassistant.util import dt as dt_util

from . import MelCloudDevice
from .const import DOMAIN


@dataclass
class MelcloudSensorEntityDescription(SensorEntityDescription):
    """Describes Melcloud sensor entity."""

    _value_fn: Callable[[Any], float] | None = None
    _enabled: Callable[[Any], bool] | None = None

    def __post_init__(self) -> None:
        """Ensure all required fields are set."""
        if self._value_fn is None:
            # pragma: no cover
            raise TypeError
        if self._enabled is None:
            # pragma: no cover
            raise TypeError
        self.value_fn = self._value_fn
        self.enabled = self._enabled


ATA_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="room_temperature",
        name="Room Temperature",
        icon="mdi:thermometer",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        _value_fn=lambda x: x.device.room_temperature,
        _enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="energy",
        name="Energy",
        icon="mdi:factory",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        _value_fn=lambda x: x.device.total_energy_consumed,
        _enabled=lambda x: x.device.has_energy_consumed_meter,
    ),
)
ATW_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="outside_temperature",
        name="Outside Temperature",
        icon="mdi:thermometer",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        _value_fn=lambda x: x.device.outside_temperature,
        _enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="tank_temperature",
        name="Tank Temperature",
        icon="mdi:thermometer",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        _value_fn=lambda x: x.device.tank_temperature,
        _enabled=lambda x: True,
    ),
)
ATW_ZONE_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="room_temperature",
        name="Room Temperature",
        icon="mdi:thermometer",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        _value_fn=lambda zone: zone.room_temperature,
        _enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="flow_temperature",
        name="Flow Temperature",
        icon="mdi:thermometer",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        _value_fn=lambda zone: zone.flow_temperature,
        _enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="return_temperature",
        name="Flow Return Temperature",
        icon="mdi:thermometer",
        unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        _value_fn=lambda zone: zone.return_temperature,
        _enabled=lambda x: True,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MELCloud device sensors based on config_entry."""
    mel_devices = hass.data[DOMAIN].get(entry.entry_id)

    entities: list[MelDeviceSensor] = [
        MelDeviceSensor(mel_device, description)
        for description in ATA_SENSORS
        for mel_device in mel_devices[DEVICE_TYPE_ATA]
        if description.enabled(mel_device)
    ] + [
        MelDeviceSensor(mel_device, description)
        for description in ATW_SENSORS
        for mel_device in mel_devices[DEVICE_TYPE_ATW]
        if description.enabled(mel_device)
    ]
    entities.extend(
        [
            AtwZoneSensor(mel_device, zone, description)
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
            for zone in mel_device.device.zones
            for description in ATW_ZONE_SENSORS
            if description.enabled(zone)
        ]
    )
    async_add_entities(entities, True)


class MelDeviceSensor(SensorEntity):
    """Representation of a Sensor."""

    entity_description: MelcloudSensorEntityDescription

    def __init__(
        self,
        api: MelCloudDevice,
        description: MelcloudSensorEntityDescription,
    ):
        """Initialize the sensor."""
        self._api = api
        self.entity_description = description

        self._attr_name = f"{api.name} {description.name}"
        self._attr_unique_id = f"{api.device.serial}-{api.device.mac}-{description.key}"
        self._attr_state_class = STATE_CLASS_MEASUREMENT

        if description.device_class == DEVICE_CLASS_ENERGY:
            self._attr_last_reset = dt_util.utc_from_timestamp(0)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._api)

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
        self,
        api: MelCloudDevice,
        zone: Zone,
        description: MelcloudSensorEntityDescription,
    ):
        """Initialize the sensor."""
        if zone.zone_index != 1:
            description.key = f"{description.key}-zone-{zone.zone_index}"
        super().__init__(api, description)
        self._zone = zone
        self._attr_name = f"{api.name} {zone.name} {description.name}"

    @property
    def state(self):
        """Return zone based state."""
        return self.entity_description.value_fn(self._zone)
