"""Support for Risco alarm zones."""

from __future__ import annotations

from collections.abc import Mapping
from itertools import chain
from typing import Any

from pyrisco.cloud.zone import Zone as CloudZone
from pyrisco.common import System
from pyrisco.local.zone import Zone as LocalZone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LocalData, is_local
from .const import DATA_COORDINATOR, DOMAIN, SYSTEM_UPDATE_SIGNAL
from .coordinator import RiscoDataUpdateCoordinator
from .entity import RiscoCloudZoneEntity, RiscoLocalZoneEntity

SYSTEM_ENTITY_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key="low_battery_trouble",
        translation_key="low_battery_trouble",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    BinarySensorEntityDescription(
        key="ac_trouble",
        translation_key="ac_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="monitoring_station_1_trouble",
        translation_key="monitoring_station_1_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="monitoring_station_2_trouble",
        translation_key="monitoring_station_2_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="monitoring_station_3_trouble",
        translation_key="monitoring_station_3_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="phone_line_trouble",
        translation_key="phone_line_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="clock_trouble",
        translation_key="clock_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="box_tamper",
        translation_key="box_tamper",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Risco alarm control panel."""
    if is_local(config_entry):
        local_data: LocalData = hass.data[DOMAIN][config_entry.entry_id]
        zone_entities = (
            entity
            for zone_id, zone in local_data.system.zones.items()
            for entity in (
                RiscoLocalBinarySensor(local_data.system.id, zone_id, zone),
                RiscoLocalAlarmedBinarySensor(local_data.system.id, zone_id, zone),
                RiscoLocalArmedBinarySensor(local_data.system.id, zone_id, zone),
            )
        )

        system_entities = (
            RiscoSystemBinarySensor(
                local_data.system.id, local_data.system.system, entity_description
            )
            for entity_description in SYSTEM_ENTITY_DESCRIPTIONS
        )

        async_add_entities(chain(system_entities, zone_entities))
    else:
        coordinator: RiscoDataUpdateCoordinator = hass.data[DOMAIN][
            config_entry.entry_id
        ][DATA_COORDINATOR]
        async_add_entities(
            RiscoCloudBinarySensor(coordinator, zone_id, zone)
            for zone_id, zone in coordinator.data.zones.items()
        )


class RiscoCloudBinarySensor(RiscoCloudZoneEntity, BinarySensorEntity):
    """Representation of a Risco cloud zone as a binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_name = None

    def __init__(
        self, coordinator: RiscoDataUpdateCoordinator, zone_id: int, zone: CloudZone
    ) -> None:
        """Init the zone."""
        super().__init__(coordinator=coordinator, suffix="", zone_id=zone_id, zone=zone)

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._zone.triggered


class RiscoLocalBinarySensor(RiscoLocalZoneEntity, BinarySensorEntity):
    """Representation of a Risco local zone as a binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_name = None

    def __init__(self, system_id: str, zone_id: int, zone: LocalZone) -> None:
        """Init the zone."""
        super().__init__(system_id=system_id, suffix="", zone_id=zone_id, zone=zone)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            **(super().extra_state_attributes or {}),
            "groups": self._zone.groups,
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._zone.triggered


class RiscoLocalAlarmedBinarySensor(RiscoLocalZoneEntity, BinarySensorEntity):
    """Representation whether a zone in Risco local is currently triggering an alarm."""

    _attr_translation_key = "alarmed"

    def __init__(self, system_id: str, zone_id: int, zone: LocalZone) -> None:
        """Init the zone."""
        super().__init__(
            system_id=system_id,
            suffix="_alarmed",
            zone_id=zone_id,
            zone=zone,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._zone.alarmed


class RiscoLocalArmedBinarySensor(RiscoLocalZoneEntity, BinarySensorEntity):
    """Representation whether a zone in Risco local is currently armed."""

    _attr_translation_key = "armed"

    def __init__(self, system_id: str, zone_id: int, zone: LocalZone) -> None:
        """Init the zone."""
        super().__init__(
            system_id=system_id,
            suffix="_armed",
            zone_id=zone_id,
            zone=zone,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._zone.armed


class RiscoSystemBinarySensor(BinarySensorEntity):
    """Risco local system binary sensor class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        system_id: str,
        system: System,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Init the sensor."""
        self._system = system
        self._property = entity_description.key
        self._attr_unique_id = f"{system_id}_{self._property}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            manufacturer="Risco",
            name=system.name,
        )
        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SYSTEM_UPDATE_SIGNAL, self.async_write_ha_state
            )
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return getattr(self._system, self._property)
