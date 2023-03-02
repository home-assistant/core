"""Support for Risco alarm zones."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyrisco.common import Zone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LocalData, RiscoDataUpdateCoordinator, is_local
from .const import DATA_COORDINATOR, DOMAIN
from .entity import RiscoCloudZoneEntity, RiscoLocalZoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Risco alarm control panel."""
    if is_local(config_entry):
        local_data: LocalData = hass.data[DOMAIN][config_entry.entry_id]
        async_add_entities(
            entity
            for zone_id, zone in local_data.system.zones.items()
            for entity in (
                RiscoLocalBinarySensor(local_data.system.id, zone_id, zone),
                RiscoLocalAlarmedBinarySensor(local_data.system.id, zone_id, zone),
                RiscoLocalArmedBinarySensor(local_data.system.id, zone_id, zone),
            )
        )
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

    def __init__(
        self, coordinator: RiscoDataUpdateCoordinator, zone_id: int, zone: Zone
    ) -> None:
        """Init the zone."""
        super().__init__(
            coordinator=coordinator, name=None, suffix="", zone_id=zone_id, zone=zone
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._zone.triggered


class RiscoLocalBinarySensor(RiscoLocalZoneEntity, BinarySensorEntity):
    """Representation of a Risco local zone as a binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, system_id: str, zone_id: int, zone: Zone) -> None:
        """Init the zone."""
        super().__init__(
            system_id=system_id, name=None, suffix="", zone_id=zone_id, zone=zone
        )

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

    def __init__(self, system_id: str, zone_id: int, zone: Zone) -> None:
        """Init the zone."""
        super().__init__(
            system_id=system_id,
            name="Alarmed",
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

    def __init__(self, system_id: str, zone_id: int, zone: Zone) -> None:
        """Init the zone."""
        super().__init__(
            system_id=system_id,
            name="Armed",
            suffix="_armed",
            zone_id=zone_id,
            zone=zone,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._zone.armed
