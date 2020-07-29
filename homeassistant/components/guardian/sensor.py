"""Sensors for the Elexa Guardian integration."""
from typing import Callable, Dict

from aioguardian import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_FAHRENHEIT, TIME_MINUTES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import GuardianEntity
from .const import (
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
)

SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_UPTIME = "uptime"
SENSORS = [
    (
        SENSOR_KIND_TEMPERATURE,
        "Temperature",
        DEVICE_CLASS_TEMPERATURE,
        None,
        TEMP_FAHRENHEIT,
    ),
    (SENSOR_KIND_UPTIME, "Uptime", None, "mdi:timer-outline", TIME_MINUTES),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Guardian switches based on a config entry."""
    async_add_entities(
        [
            GuardianSensor(
                entry,
                hass.data[DOMAIN][DATA_CLIENT][entry.entry_id],
                hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id],
                kind,
                name,
                device_class,
                icon,
                unit,
            )
            for kind, name, device_class, icon, unit in SENSORS
        ],
        True,
    )


class GuardianSensor(GuardianEntity):
    """Define a generic Guardian sensor."""

    def __init__(
        self,
        entry: ConfigEntry,
        client: Client,
        coordinators: Dict[str, DataUpdateCoordinator],
        kind: str,
        name: str,
        device_class: str,
        icon: str,
        unit: str,
    ) -> None:
        """Initialize."""
        super().__init__(entry, client, coordinators, kind, name, device_class, icon)

        self._state = None
        self._unit = unit

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            return self._coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].last_update_success
        if self._kind == SENSOR_KIND_UPTIME:
            return self._coordinators[API_SYSTEM_DIAGNOSTICS].last_update_success
        return False

    @property
    def state(self) -> str:
        """Return the sensor state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    async def _async_internal_added_to_hass(self) -> None:
        """Register API interest (and related tasks) when the entity is added."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            self.async_add_coordinator_update_listener(API_SYSTEM_ONBOARD_SENSOR_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            self._state = self._coordinators[API_SYSTEM_ONBOARD_SENSOR_STATUS].data[
                "temperature"
            ]
        elif self._kind == SENSOR_KIND_UPTIME:
            self._state = self._coordinators[API_SYSTEM_DIAGNOSTICS].data["uptime"]
