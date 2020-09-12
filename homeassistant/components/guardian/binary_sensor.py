"""Binary sensors for the Elexa Guardian integration."""
from typing import Callable, Dict

from aioguardian import Client

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import GuardianEntity
from .const import (
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_WIFI_STATUS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)

ATTR_CONNECTED_CLIENTS = "connected_clients"

SENSOR_KIND_AP_INFO = "ap_enabled"
SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSORS = [
    (SENSOR_KIND_AP_INFO, "Onboard AP Enabled", DEVICE_CLASS_CONNECTIVITY),
    (SENSOR_KIND_LEAK_DETECTED, "Leak Detected", "moisture"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Guardian switches based on a config entry."""
    async_add_entities(
        [
            GuardianBinarySensor(
                entry,
                hass.data[DOMAIN][DATA_CLIENT][entry.entry_id],
                hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id],
                kind,
                name,
                device_class,
            )
            for kind, name, device_class in SENSORS
        ],
        True,
    )


class GuardianBinarySensor(GuardianEntity, BinarySensorEntity):
    """Define a generic Guardian sensor."""

    def __init__(
        self,
        entry: ConfigEntry,
        client: Client,
        coordinators: Dict[str, DataUpdateCoordinator],
        kind: str,
        name: str,
        device_class: str,
    ) -> None:
        """Initialize."""
        super().__init__(entry, client, coordinators, kind, name, device_class, None)

        self._is_on = True

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        if self._kind == SENSOR_KIND_AP_INFO:
            return self._coordinators[API_WIFI_STATUS].last_update_success
        if self._kind == SENSOR_KIND_LEAK_DETECTED:
            return self._coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].last_update_success
        return False

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self._is_on

    async def _async_internal_added_to_hass(self) -> None:
        if self._kind == SENSOR_KIND_AP_INFO:
            self.async_add_coordinator_update_listener(API_WIFI_STATUS)
        elif self._kind == SENSOR_KIND_LEAK_DETECTED:
            self.async_add_coordinator_update_listener(API_SYSTEM_ONBOARD_SENSOR_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self._kind == SENSOR_KIND_AP_INFO:
            self._is_on = self._coordinators[API_WIFI_STATUS].data["station_connected"]
            self._attrs.update(
                {
                    ATTR_CONNECTED_CLIENTS: self._coordinators[API_WIFI_STATUS].data[
                        "ap_clients"
                    ]
                }
            )
        elif self._kind == SENSOR_KIND_LEAK_DETECTED:
            self._is_on = self._coordinators[API_SYSTEM_ONBOARD_SENSOR_STATUS].data[
                "wet"
            ]
