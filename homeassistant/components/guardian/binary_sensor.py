"""Binary sensors for the Elexa Guardian integration."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback

from . import GuardianEntity
from .const import (
    DATA_CLIENT,
    DATA_SENSOR_STATUS,
    DATA_WIFI_STATUS,
    DOMAIN,
    SENSOR_KIND_AP_INFO,
    SENSOR_KIND_LEAK_DETECTED,
)

ATTR_CONNECTED_CLIENTS = "connected_clients"

SENSORS = [
    (SENSOR_KIND_AP_INFO, "Onboard AP Enabled", "connectivity"),
    (SENSOR_KIND_LEAK_DETECTED, "Leak Detected", "moisture"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Guardian switches based on a config entry."""
    guardian = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            GuardianBinarySensor(guardian, kind, name, device_class)
            for kind, name, device_class in SENSORS
        ],
        True,
    )


class GuardianBinarySensor(GuardianEntity, BinarySensorEntity):
    """Define a generic Guardian sensor."""

    def __init__(self, guardian, kind, name, device_class):
        """Initialize."""
        super().__init__(guardian, kind, name, device_class, None)

        self._is_on = True

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._is_on

    @callback
    def _update_from_latest_data(self):
        """Update the entity."""
        if self._kind == SENSOR_KIND_AP_INFO:
            self._is_on = self._guardian.data[DATA_WIFI_STATUS]["ap_enabled"]
            self._attrs.update(
                {
                    ATTR_CONNECTED_CLIENTS: self._guardian.data[DATA_WIFI_STATUS][
                        "ap_clients"
                    ]
                }
            )
        elif self._kind == SENSOR_KIND_LEAK_DETECTED:
            self._is_on = self._guardian.data[DATA_SENSOR_STATUS]["wet"]
