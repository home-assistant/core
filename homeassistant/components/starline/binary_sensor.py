"""Reads vehicle status from StarLine API."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="hbrake",
        translation_key="hand_brake",
    ),
    BinarySensorEntityDescription(
        key="hood",
        translation_key="hood",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    BinarySensorEntityDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    BinarySensorEntityDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="door",
        translation_key="doors",
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    BinarySensorEntityDescription(
        key="run",
        translation_key="ignition",
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="r_start",
        translation_key="autostart",
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="hfree",
        translation_key="handsfree",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="neutral",
        translation_key="neutral",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="arm_moving_pb",
        translation_key="moving_ban",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the StarLine sensors."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = [
        sensor
        for device in account.api.devices.values()
        for description in BINARY_SENSOR_TYPES
        if description.key in device.car_state
        if (sensor := StarlineSensor(account, device, description)).is_on is not None
    ]
    async_add_entities(entities)


class StarlineSensor(StarlineEntity, BinarySensorEntity):
    """Representation of a StarLine binary sensor."""

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(account, device, description.key)
        self.entity_description = description

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._device.car_state.get(self._key)
