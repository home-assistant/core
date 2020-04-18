"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import logging
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_RATE_KILOBYTES_PER_SECOND
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CONNECTION_SENSORS,
    DOMAIN,
    SENSOR_DEVICE_CLASS,
    SENSOR_ICON,
    SENSOR_NAME,
    SENSOR_UNIT,
    TEMPERATURE_SENSOR_TEMPLATE,
)
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""
    router = hass.data[DOMAIN][entry.unique_id]
    entities = []

    for sensor_name in router.sensors_temperature:
        entities.append(
            FreeboxSensor(
                router,
                sensor_name,
                {**TEMPERATURE_SENSOR_TEMPLATE, SENSOR_NAME: f"Freebox {sensor_name}"},
            )
        )

    for sensor_key in CONNECTION_SENSORS:
        entities.append(
            FreeboxSensor(router, sensor_key, CONNECTION_SENSORS[sensor_key])
        )

    async_add_entities(entities, True)


class FreeboxSensor(Entity):
    """Representation of a Freebox sensor."""

    def __init__(
        self, router: FreeboxRouter, sensor_type: str, sensor: Dict[str, any]
    ) -> None:
        """Initialize a Freebox sensor."""
        self._state = None
        self._router = router
        self._sensor_type = sensor_type
        self._name = sensor[SENSOR_NAME]
        self._unit = sensor[SENSOR_UNIT]
        self._icon = sensor[SENSOR_ICON]
        self._device_class = sensor[SENSOR_DEVICE_CLASS]
        self._unique_id = f"{self._router.mac} {self._name}"

        self._unsub_dispatcher = None

    def update(self) -> None:
        """Update the Freebox sensor."""
        state = self._router.sensors[self._sensor_type]
        if self._unit == DATA_RATE_KILOBYTES_PER_SECOND:
            self._state = round(state / 1000, 2)
        else:
            self._state = state

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit."""
        return self._unit

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._device_class

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return self._router.device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self._router.signal_sensor_update, self.async_on_demand_update
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()
