"""Support for Aladdin Connect Genie sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from genie_partner_sdk.client import AladdinConnectClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import api
from .const import DOMAIN
from .model import GarageDoor

if TYPE_CHECKING:
    from . import AladdinConnectConfigEntry


@dataclass(frozen=True, kw_only=True)
class AccSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for Aladdin Connect."""

    value_fn: Callable[[AladdinConnectClient, str, int], float | None]


SENSOR_TYPES: tuple[AccSensorEntityDescription, ...] = (
    AccSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=AladdinConnectClient.get_battery_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AladdinConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aladdin Connect sensor devices."""

    session: api.AsyncConfigEntryAuth = entry.runtime_data
    acc = AladdinConnectClient(session)

    doors = await acc.get_doors()
    if doors is None:
        return

    entities = [
        AladdinConnectSensor(acc, door, description)
        for door in doors
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class AladdinConnectSensor(SensorEntity):
    """A sensor implementation for Aladdin Connect device."""

    entity_description: AccSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        acc: AladdinConnectClient,
        device: GarageDoor,
        description: AccSensorEntityDescription,
    ) -> None:
        """Initialize a sensor for an Aladdin Connect device."""
        self._device_id = device.device_id
        self._number = device.door_number
        self._acc = acc
        self.entity_description = description
        self._attr_unique_id = f"{device.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer="Overhead Door",
        )
        self._attr_native_value: float | None = None

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._acc.update_door(self._device_id, self._number)
        self._attr_native_value = self.entity_description.value_fn(
            self._acc, self._device_id, self._number
        )
