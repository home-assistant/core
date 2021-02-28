"""Platform for sensor integration."""
from enum import Enum
import logging

import smarttub
import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubSensorBase

_LOGGER = logging.getLogger(__name__)


ATTR_DURATION = "duration"
ATTR_LAST_UPDATED = "last_updated"
ATTR_MODE = "mode"
ATTR_START_HOUR = "start_hour"

SUPPORT_PRIMARY_FILTRATION = 1
SUPPORT_SECONDARY_FILTRATION = 2

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


async def async_setup_entry(hass, entry, async_add_entities):
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

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        "set_primary_filtration",
        SET_PRIMARY_FILTRATION_SCHEMA,
        "async_set_primary_filtration",
        [SUPPORT_PRIMARY_FILTRATION]
    )

    platform.async_register_entity_service(
        "set_secondary_filtration",
        SET_SECONDARY_FILTRATION_SCHEMA,
        "async_set_secondary_filtration",
        [SUPPORT_SECONDARY_FILTRATION]
    )


class SmartTubSensor(SmartTubSensorBase):
    """Generic class for SmartTub status sensors."""

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        if isinstance(self._state, Enum):
            return self._state.name.lower()
        return self._state.lower()


class SmartTubPrimaryFiltrationCycle(SmartTubSensor):
    """The primary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "primary filtration cycle", "primary_filtration"
        )

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.status.name.lower()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = self._state
        return {
            ATTR_DURATION: state.duration,
            ATTR_LAST_UPDATED: state.last_updated.isoformat(),
            ATTR_MODE: state.mode.name.lower(),
            ATTR_START_HOUR: state.start_hour,
        }

    @property
    def supported_features(self):
        return SUPPORT_PRIMARY_FILTRATION

    async def async_set_primary_filtration(self, **kwargs):
        """Update primary filtration settings."""
        await self._state.set(
            duration=kwargs.get(ATTR_DURATION),
            start_hour=kwargs.get(ATTR_START_HOUR),
        )


class SmartTubSecondaryFiltrationCycle(SmartTubSensor):
    """The secondary filtration cycle."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(
            coordinator, spa, "Secondary Filtration Cycle", "secondary_filtration"
        )

    @property
    def state(self) -> str:
        """Return the current state of the sensor."""
        return self._state.status.name.lower()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state = self._state
        return {
            ATTR_LAST_UPDATED: state.last_updated.isoformat(),
            ATTR_MODE: state.mode.name.lower(),
        }

    @property
    def supported_features(self):
        return SUPPORT_SECONDARY_FILTRATION

    async def async_set_secondary_filtration(self, **kwargs):
        """Update primary filtration settings."""
        mode = smarttub.SpaSecondaryFiltrationCycle.SecondaryFiltrationMode[
            kwargs[ATTR_MODE].upper()
        ]
        await self._state.set_mode(mode)
