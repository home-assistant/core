"""Platform for sensor integration."""

from enum import Enum
from typing import Any

import smarttub
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .controller import SmartTubConfigEntry
from .entity import SmartTubOnboardSensorBase

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

SET_SECONDARY_FILTRATION_SCHEMA: VolDictType = {
    vol.Required(ATTR_MODE): vol.In(
        {
            mode.name.lower()
            for mode in smarttub.SpaSecondaryFiltrationCycle.SecondaryFiltrationMode
        }
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartTubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities for the sensors in the tub."""

    controller = entry.runtime_data

    entities = []
    for spa in controller.spas:
        entities.extend(
            [
                SmartTubBuiltinSensor(controller.coordinator, spa, "State", "state"),
                SmartTubBuiltinSensor(
                    controller.coordinator, spa, "Flow Switch", "flow_switch"
                ),
                SmartTubBuiltinSensor(controller.coordinator, spa, "Ozone", "ozone"),
                SmartTubBuiltinSensor(controller.coordinator, spa, "UV", "uv"),
                SmartTubBuiltinSensor(
                    controller.coordinator, spa, "Blowout Cycle", "blowout_cycle"
                ),
                SmartTubBuiltinSensor(
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


class SmartTubBuiltinSensor(SmartTubOnboardSensorBase, SensorEntity):
    """Generic class for SmartTub status sensors."""

    @property
    def native_value(self) -> str | None:
        """Return the current state of the sensor."""
        if self._state is None:
            return None

        if isinstance(self._state, Enum):
            return self._state.name.lower()

        return self._state.lower()


class SmartTubPrimaryFiltrationCycle(SmartTubBuiltinSensor):
    """The primary filtration cycle."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[dict[str, Any]], spa: smarttub.Spa
    ) -> None:
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
    def extra_state_attributes(self) -> dict[str, Any]:
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


class SmartTubSecondaryFiltrationCycle(SmartTubBuiltinSensor):
    """The secondary filtration cycle."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[dict[str, Any]], spa: smarttub.Spa
    ) -> None:
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
    def extra_state_attributes(self) -> dict[str, Any]:
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
