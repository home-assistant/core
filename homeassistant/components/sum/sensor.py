"""Support for displaying sum values."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:calculator"
DEFAULT_NAME = "Sum sensor"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_ENTITY_IDS): cv.entity_ids,
        vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize sum config entry."""
    registry = er.async_get(hass)
    entity_ids = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITY_IDS]
    )
    round_digits = int(config_entry.options[CONF_ROUND_DIGITS])

    async_add_entities(
        [
            SumSensor(
                entity_ids,
                config_entry.title,
                round_digits,
                config_entry.entry_id,
            )
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the min/max/mean sensor."""
    entity_ids: list[str] = config[CONF_ENTITY_IDS]
    name: str = config[CONF_NAME]
    round_digits: float = config[CONF_ROUND_DIGITS]
    unique_id: str | None = config.get(CONF_UNIQUE_ID)

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    async_add_entities([SumSensor(entity_ids, name, round_digits, unique_id)])


def calc_sum(sensor_values: list[tuple[str, Any]], round_digits: int) -> float | None:
    """Calculate sum value, not honoring unknown states."""
    result = []
    for _, sensor_value in sensor_values:
        if sensor_value in [STATE_UNKNOWN, STATE_UNAVAILABLE]:
            return None
        result.append(sensor_value)

    return round(sum(result), round_digits)


class SumSensor(SensorEntity):
    """Representation of a sum sensor."""

    _attr_icon = ICON
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entity_ids: list[str],
        name: str,
        round_digits: float,
        unique_id: str | None,
    ) -> None:
        """Initialize the sum sensor."""
        self._attr_unique_id = unique_id
        self._entity_ids = entity_ids
        self._round_digits = int(round_digits)

        self._attr_name = name

        self.sum: float | None = None
        self.last: float | None = None
        self.last_entity_id: str | None = None
        self.count_sensors = len(self._entity_ids)
        self._unit_of_measurement = None
        self.states: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Handle added to Hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, self._async_sum_sensor_state_listener
            )
        )

        # Replay current state of source entities
        for entity_id in self._entity_ids:
            state = self.hass.states.get(entity_id)
            state_event = Event("", {"entity_id": entity_id, "new_state": state})
            self._async_sum_sensor_state_listener(state_event, update_state=False)

        self._calc_values()

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.sum

    @callback
    def _async_sum_sensor_state_listener(
        self, event: EventType, update_state: bool = True
    ) -> None:
        """Handle the sensor state changes."""
        new_state: State | None = event.data.get("new_state")
        entity: str = event.data["entity_id"]

        if (
            new_state is None
            or new_state.state is None
            or new_state.state
            in [
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ]
        ):
            self.states[entity] = STATE_UNKNOWN
            if not update_state:
                return

            self._calc_values()
            self.async_write_ha_state()
            return

        if self._unit_of_measurement is None:
            self._unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            )

        if self._unit_of_measurement != new_state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        ):
            _LOGGER.warning(
                "Units of measurement do not match for entity %s", self.entity_id
            )

        try:
            self.states[entity] = float(new_state.state)
            self.last = float(new_state.state)
            self.last_entity_id = entity
        except ValueError:
            _LOGGER.warning(
                "Unable to store state. Only numerical states are supported"
            )

        if not update_state:
            return

        self._calc_values()
        self.async_write_ha_state()

    @callback
    def _calc_values(self) -> None:
        """Calculate the values."""
        sensor_values = [
            (entity_id, self.states[entity_id])
            for entity_id in self._entity_ids
            if entity_id in self.states
        ]

        self.sum = calc_sum(sensor_values, self._round_digits)
