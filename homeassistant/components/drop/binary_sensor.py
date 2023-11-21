"""Support for DROP binary sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_TYPE,
    DEV_HUB,
    DEV_LEAK_DETECTOR,
    DEV_PROTECTION_VALVE,
    DEV_PUMP_CONTROLLER,
    DEV_RO_FILTER,
    DEV_SALT_SENSOR,
    DEV_SOFTENER,
    DOMAIN as DROP_DOMAIN,
)
from .entity import DROP_Entity

_LOGGER = logging.getLogger(__name__)

WATER_ICON = "mdi:water"
LEAK_ICON = "mdi:pipe-leak"
SALT_ICON = "mdi:shaker"
PUMP_ON_ICON = "mdi:water-pump"
PUMP_OFF_ICON = "mdi:water-pump-off"
NOTIFICATION_ICON = "mdi:bell-ring"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DROP binary sensors from config entry."""
    _LOGGER.debug(
        "Set up binary sensor for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    entities = []
    if config_entry.data[CONF_DEVICE_TYPE] == DEV_HUB:
        entities.extend(
            [
                DROP_PendingNotificationSensor(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
                DROP_LeakSensor(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    elif (
        config_entry.data[CONF_DEVICE_TYPE] == DEV_LEAK_DETECTOR
        or config_entry.data[CONF_DEVICE_TYPE] == DEV_PROTECTION_VALVE
        or config_entry.data[CONF_DEVICE_TYPE] == DEV_RO_FILTER
    ):
        entities.extend(
            [
                DROP_LeakSensor(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    elif config_entry.data[CONF_DEVICE_TYPE] == DEV_SALT_SENSOR:
        entities.extend(
            [
                DROP_SaltSensor(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    elif config_entry.data[CONF_DEVICE_TYPE] == DEV_SOFTENER:
        entities.extend(
            [
                DROP_ReserveInUseSensor(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    elif config_entry.data[CONF_DEVICE_TYPE] == DEV_PUMP_CONTROLLER:
        entities.extend(
            [
                DROP_PumpSensor(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
                DROP_LeakSensor(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )

    async_add_entities(entities)


class DROP_PendingNotificationSensor(DROP_Entity, BinarySensorEntity):
    """Monitors the pending notification sensor status."""

    _attr_icon = NOTIFICATION_ICON
    _attr_translation_key = "pending_notification"

    def __init__(self, device) -> None:
        """Initialize the pending notification sensor."""
        super().__init__("pending_notification", device)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the pending notification sensor."""
        if self._device.pending_notification is None:
            return None
        return self._device.pending_notification is True


class DROP_LeakSensor(DROP_Entity, BinarySensorEntity):
    """Monitors the leak sensor status."""

    _attr_icon = LEAK_ICON
    _attr_translation_key = "leak"

    def __init__(self, device) -> None:
        """Initialize the current flow rate sensor."""
        super().__init__("leak", device)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the leak sensor."""
        if self._device.leak is None:
            return None
        return self._device.leak is True


class DROP_SaltSensor(DROP_Entity, BinarySensorEntity):
    """Monitors the salt sensor status."""

    _attr_icon = SALT_ICON
    _attr_translation_key = "salt"

    def __init__(self, device) -> None:
        """Initialize the current flow rate sensor."""
        super().__init__("salt", device)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the salt sensor."""
        if self._device.salt is None:
            return None
        return self._device.salt is True


class DROP_PumpSensor(DROP_Entity, BinarySensorEntity):
    """Monitors the pump status."""

    _attr_icon = PUMP_ON_ICON
    _attr_translation_key = "pump"

    def __init__(self, device) -> None:
        """Initialize the current pump status."""
        super().__init__("pump", device)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the pump sensor."""
        if self._device.pump is None:
            return None
        return self._device.pump is True


class DROP_ReserveInUseSensor(DROP_Entity, BinarySensorEntity):
    """Monitors the softener reserve in use status."""

    _attr_icon = WATER_ICON
    _attr_translation_key = "reserve_in_use"

    def __init__(self, device) -> None:
        """Initialize the softener reserve in use status."""
        super().__init__("reserve_in_use", device)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the softener reserve in use sensor."""
        if self._device.reserve_in_use is None:
            return None
        return self._device.reserve_in_use is True
