"""Support for MelCloud device sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pymelcloud import DEVICE_TYPE_ATA, DEVICE_TYPE_ATW
from pymelcloud.atw_device import Zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MelCloudDevice
from .const import DOMAIN


@dataclass
class MelcloudRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], float]
    enabled: Callable[[Any], bool]


@dataclass
class MelcloudSensorEntityDescription(
    SensorEntityDescription, MelcloudRequiredKeysMixin
):
    """Describes Melcloud sensor entity."""


ATA_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda x: x.device.room_temperature,
        enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="energy",
        icon="mdi:factory",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda x: x.device.total_energy_consumed,
        enabled=lambda x: x.device.has_energy_consumed_meter,
    ),
    MelcloudSensorEntityDescription(
        key="daily_energy",
        translation_key="daily_energy",
        icon="mdi:factory",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda x: x.device.daily_energy_consumed,
        enabled=lambda x: True,
    ),
)
ATW_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda x: x.device.outside_temperature,
        enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="tank_temperature",
        translation_key="tank_temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda x: x.device.tank_temperature,
        enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="daily_energy",
        translation_key="daily_energy",
        icon="mdi:factory",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda x: x.device.daily_energy_consumed,
        enabled=lambda x: True,
    ),
)
ATW_ZONE_SENSORS: tuple[MelcloudSensorEntityDescription, ...] = (
    MelcloudSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda zone: zone.room_temperature,
        enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="flow_temperature",
        translation_key="flow_temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda zone: zone.flow_temperature,
        enabled=lambda x: True,
    ),
    MelcloudSensorEntityDescription(
        key="return_temperature",
        translation_key="return_temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda zone: zone.return_temperature,
        enabled=lambda x: True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
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
    _attr_has_entity_name = True

    def __init__(
        self,
        api: MelCloudDevice,
        description: MelcloudSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._api = api
        self.entity_description = description

        self._attr_unique_id = f"{api.device.serial}-{api.device.mac}-{description.key}"
        self._attr_device_info = api.device_info

        if description.device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._api)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()


class AtwZoneSensor(MelDeviceSensor):
    """Air-to-Air device sensor."""

    def __init__(
        self,
        api: MelCloudDevice,
        zone: Zone,
        description: MelcloudSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        if zone.zone_index != 1:
            description.key = f"{description.key}-zone-{zone.zone_index}"
        super().__init__(api, description)

        dev = api.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{dev.mac}-{dev.serial}-{zone.zone_index}")},
            connections={(CONNECTION_NETWORK_MAC, dev.mac)},
            manufacturer="Mitsubishi Electric",
            model="ATW zone device",
            name=f"{api.name} {zone.name}",
            via_device=(DOMAIN, f"{dev.mac}-{dev.serial}"),
        )
        self._zone = zone

    @property
    def native_value(self) -> float | None:
        """Return zone based state."""
        return self.entity_description.value_fn(self._zone)
