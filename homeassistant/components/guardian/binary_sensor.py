"""Binary sensors for the Elexa Guardian integration."""
from typing import Callable

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOVING,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from . import PairedSensorEntity, ValveControllerEntity
from .const import (
    API_SENSOR_PAIRED_SENSOR_STATUS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_WIFI_STATUS,
    DATA_COORDINATOR,
    DOMAIN,
)

ATTR_CONNECTED_CLIENTS = "connected_clients"

SENSOR_KIND_AP_INFO = "ap_enabled"
SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSOR_KIND_MOVED = "moved"

PAIRED_SENSOR_SENSORS = [
    (SENSOR_KIND_LEAK_DETECTED, "Leak Detected", DEVICE_CLASS_MOISTURE),
    (SENSOR_KIND_MOVED, "Recently Moved", DEVICE_CLASS_MOVING),
]

VALVE_CONTROLLER_SENSORS = [
    (SENSOR_KIND_AP_INFO, "Onboard AP Enabled", DEVICE_CLASS_CONNECTIVITY),
    (SENSOR_KIND_LEAK_DETECTED, "Leak Detected", DEVICE_CLASS_MOISTURE),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Guardian switches based on a config entry."""
    sensors = []

    for kind, name, device_class in VALVE_CONTROLLER_SENSORS:
        sensors.append(
            ValveControllerBinarySensor(
                entry,
                hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id],
                kind,
                name,
                device_class,
                None,
            )
        )

    for ps_coordinator in hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
        API_SENSOR_PAIRED_SENSOR_STATUS
    ].values():
        for kind, name, device_class in PAIRED_SENSOR_SENSORS:
            sensors.append(
                PairedSensorBinarySensor(
                    entry, ps_coordinator, kind, name, device_class, None,
                )
            )

    async_add_entities(sensors, True)


class PairedSensorBinarySensor(PairedSensorEntity, BinarySensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return True

    async def _async_internal_added_to_hass(self) -> None:
        """Add an API listener."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._async_update_state_callback)
        )

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self._kind == SENSOR_KIND_LEAK_DETECTED:
            self._is_on = self._coordinator.data["wet"]
        elif self._kind == SENSOR_KIND_MOVED:
            self._is_on = self._coordinator.data["moved"]


class ValveControllerBinarySensor(ValveControllerEntity, BinarySensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

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
        return self._coordinators[API_WIFI_STATUS].data["ap_enabled"]

    async def _async_internal_added_to_hass(self) -> None:
        """Add an API listener."""
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
