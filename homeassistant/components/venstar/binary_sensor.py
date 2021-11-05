"""Alarm sensors for the Venstar Thermostat."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from . import VenstarEntity
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Vensar device binary_sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if coordinator.client.alerts is None:
        return
    sensors = [
        VenstarBinarySensor(coordinator, config_entry, alert["name"])
        for alert in coordinator.client.alerts
    ]

    async_add_entities(sensors, True)


class VenstarBinarySensor(VenstarEntity, BinarySensorEntity):
    """Represent a Venstar alert."""

    _attr_device_class = DEVICE_CLASS_PROBLEM

    def __init__(self, coordinator, config, alert):
        """Initialize the alert."""
        super().__init__(coordinator, config)
        self.alert = alert
        self._config = config
        self._unique_id = f"{self._config.entry_id}_{self.alert.replace(' ', '_')}"
        self._name = f"{self._client.name} {self.alert}"

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        for alert in self._client.alerts:
            if alert["name"] == self.alert:
                return alert["active"]
