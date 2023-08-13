"""Alarm sensors for the Venstar Thermostat."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VenstarEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Venstar device binary_sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if coordinator.client.alerts is None:
        return

    entities: list[VenstarEntity] = [
        *(
            VenstarAlertBinarySensor(coordinator, config_entry, alert["name"])
            for alert in coordinator.client.alerts
        ),
        VenstarFanBinarySensor(coordinator, config_entry),
    ]

    async_add_entities(entities)


class VenstarAlertBinarySensor(VenstarEntity, BinarySensorEntity):
    """Represent a Venstar alert."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, config, alert) -> None:
        """Initialize the alert."""
        super().__init__(coordinator, config)
        self.alert = alert
        self._attr_unique_id = f"{config.entry_id}_{alert.replace(' ', '_')}"
        self._attr_name = f"{self._client.name} {alert}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        for alert in self._client.alerts:
            if alert["name"] == self.alert:
                return alert["active"]

        return None


class VenstarFanBinarySensor(VenstarEntity, BinarySensorEntity):
    """Represent the on/off state of a Venstar fan."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, config) -> None:
        """Initialize the alert."""
        super().__init__(coordinator, config)
        self._attr_unique_id = f"{config.entry_id}_fan"
        self._attr_name = f"{self._client.name} Fan"

    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        return self._client.fanstate
