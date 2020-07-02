"""Sensors for the Elexa Guardian integration."""
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_FAHRENHEIT, TIME_MINUTES
from homeassistant.core import callback

from . import Guardian, GuardianEntity
from .const import (
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    DATA_CLIENT,
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
    (SENSOR_KIND_UPTIME, "Uptime", None, "mdi:timer", TIME_MINUTES),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Guardian switches based on a config entry."""
    guardian = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            GuardianSensor(guardian, kind, name, device_class, icon, unit)
            for kind, name, device_class, icon, unit in SENSORS
        ],
        True,
    )


class GuardianSensor(GuardianEntity):
    """Define a generic Guardian sensor."""

    def __init__(
        self,
        guardian: Guardian,
        kind: str,
        name: str,
        device_class: str,
        icon: str,
        unit: str,
    ):
        """Initialize."""
        super().__init__(guardian, kind, name, device_class, icon)

        self._state = None
        self._unit = unit

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @callback
    def _async_update_from_latest_data(self):
        """Update the entity."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            self._state = self._guardian.data[API_SYSTEM_ONBOARD_SENSOR_STATUS][
                "temperature"
            ]
        elif self._kind == SENSOR_KIND_UPTIME:
            self._state = self._guardian.data[API_SYSTEM_DIAGNOSTICS]["uptime"]

    async def async_added_to_hass(self):
        """Register API interest (and related tasks) when the entity is added."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            await self._guardian.async_register_api_interest(
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            )

        self._async_setup_listeners()

    async def async_will_remove_from_hass(self) -> None:
        """Deregister API interest (and related tasks) when the entity is removed."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            self._guardian.async_deregister_api_interest(
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            )

        self._guardian.async_remove_listener(self._update_callback)
