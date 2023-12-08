"""Platform for sensor integration."""
from enum import Enum

import smarttub
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubSensorBase

# the desired duration, in hours, of the cycle
ATTR_DURATION = "duration"
ATTR_CYCLE_LAST_UPDATED = "cycle_last_updated"
ATTR_MODE = "mode"
# the hour of the day at which to start the cycle (0-23)
ATTR_START_HOUR = "start_hour"

SET_PRIMARY_FILTRATION_SCHEMA = vol.All(
    cv.has_at_least_one_key(ATTR_DURATION, ATTR_START_HOUR),
    cv.make_entity_service_schema(
        {
            vol.Optional(ATTR_DURATION): vol.All(int, vol.Range(min=1, max=24)),
            vol.Optional(ATTR_START_HOUR): vol.All(int, vol.Range(min=0, max=23)),
        },
    ),
)

SET_SECONDARY_FILTRATION_SCHEMA = {
    vol.Required(ATTR_MODE): vol.In(
        {
            mode.name.lower()
            for mode in smarttub.SpaSecondaryFiltrationCycle.SecondaryFiltrationMode
        }
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities for the sensors in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = []
    for spa in controller.spas:
        entities.extend(
            [
                SmartTubSensor(controller.coordinator, spa, "State", "state"),
                SmartTubSensor(
                    controller.coordinator, spa, "Flow Switch", "flow_switch"
                ),
                SmartTubSensor(controller.coordinator, spa, "Ozone", "ozone"),
                SmartTubSensor(controller.coordinator, spa, "UV", "uv"),
                SmartTubSensor(
                    controller.coordinator, spa, "Blowout Cycle", "blowout_cycle"
                ),
                SmartTubSensor(
                    controller.coordinator, spa, "Cleanup Cycle", "cleanup_cycle"
                ),
                SmartTubPrimaryFiltrationCycle(controller.coordinator, spa),
                SmartTubSecondaryFiltrationCycle(controller.coordinator, spa),
            ]
        )

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "set_primary_filtration",
        SET_PRIMARY_FILTRATION_SCHEMA,
        "async_set_primary_filtration",
    )

    platform.async_register_entity_service(
        "set_secondary_filtration",
        SET_SECONDARY_FILTRATION_SCHEMA,
        "async_set_secondary_filtration",
    )


class SmartTubSensor(SmartTubSensorBase, SensorEntity):
    """Generic class for SmartTub status sensors."""

    @property
    def native_value(self) -> str | None:
        """Return the current state of the sensor."""
        if self._state is None:
            return None

        if isinstance(self._state, Enum):
            return self._state.name.lower()

        return self._state.lower()


class SmartTubPrimaryFiltrationCycle(SmartTubSensor):
    """The primary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "Primary Filtration Cycle", "primary_filtration"
        )

    @property
    def cycle(self) -> smarttub.SpaPrimaryFiltrationCycle:
        """Return the underlying smarttub.SpaPrimaryFiltrationCycle object."""
        return self._state

    @property
    def native_value(self) -> str:
        """Return the current state of the sensor."""
        return self.cycle.status.name.lower()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DURATION: self.cycle.duration,
            ATTR_CYCLE_LAST_UPDATED: self.cycle.last_updated.isoformat(),
            ATTR_MODE: self.cycle.mode.name.lower(),
            ATTR_START_HOUR: self.cycle.start_hour,
        }

    async def async_set_primary_filtration(self, **kwargs):
        """Update primary filtration settings."""
        await self.cycle.set(
            duration=kwargs.get(ATTR_DURATION),
            start_hour=kwargs.get(ATTR_START_HOUR),
        )
        await self.coordinator.async_request_refresh()


class SmartTubSecondaryFiltrationCycle(SmartTubSensor):
    """The secondary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "Secondary Filtration Cycle", "secondary_filtration"
        )

    @property
    def cycle(self) -> smarttub.SpaSecondaryFiltrationCycle:
        """Return the underlying smarttub.SpaSecondaryFiltrationCycle object."""
        return self._state

    @property
    def native_value(self) -> str:
        """Return the current state of the sensor."""
        return self.cycle.status.name.lower()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_CYCLE_LAST_UPDATED: self.cycle.last_updated.isoformat(),
            ATTR_MODE: self.cycle.mode.name.lower(),
        }

    async def async_set_secondary_filtration(self, **kwargs):
        """Update primary filtration settings."""
        mode = smarttub.SpaSecondaryFiltrationCycle.SecondaryFiltrationMode[
            kwargs[ATTR_MODE].upper()
        ]
        await self.cycle.set_mode(mode)
        await self.coordinator.async_request_refresh()
