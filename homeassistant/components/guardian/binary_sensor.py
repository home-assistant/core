"""Binary sensors for the Elexa Guardian integration."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback

from . import GuardianEntity
from .const import (
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_WIFI_STATUS,
    DATA_COORDINATOR,
    DOMAIN,
)

ATTR_CONNECTED_CLIENTS = "connected_clients"

SENSOR_KIND_AP_INFO = "ap_enabled"
SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSORS = [
    (SENSOR_KIND_AP_INFO, "Onboard AP Enabled", "connectivity"),
    (SENSOR_KIND_LEAK_DETECTED, "Leak Detected", "moisture"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Guardian switches based on a config entry."""
    guardian = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]
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
    def _async_update_from_latest_data(self):
        """Update the entity."""
        if self._kind == SENSOR_KIND_AP_INFO:
            self._is_on = self._guardian.data[API_WIFI_STATUS]["ap_enabled"]
            self._attrs.update(
                {
                    ATTR_CONNECTED_CLIENTS: self._guardian.data[API_WIFI_STATUS][
                        "ap_clients"
                    ]
                }
            )
        elif self._kind == SENSOR_KIND_LEAK_DETECTED:
            self._is_on = self._guardian.data[API_SYSTEM_ONBOARD_SENSOR_STATUS]["wet"]

    async def async_added_to_hass(self):
        """Register API interest (and related tasks) when the entity is added."""
        if self._kind == SENSOR_KIND_AP_INFO:
            await self._guardian.async_register_api_interest(API_WIFI_STATUS)
        elif self._kind == SENSOR_KIND_LEAK_DETECTED:
            await self._guardian.async_register_api_interest(
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            )

        self._async_internal_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Deregister API interest (and related tasks) when the entity is removed."""
        if self._kind == SENSOR_KIND_AP_INFO:
            self._guardian.async_deregister_api_interest(API_WIFI_STATUS)
        elif self._kind == SENSOR_KIND_LEAK_DETECTED:
            self._guardian.async_deregister_api_interest(
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            )
