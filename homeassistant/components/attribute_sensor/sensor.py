"""Support for creating a sensor based on an attribute value."""
from __future__ import annotations

from datetime import datetime
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    EventType,
    StateType,
)

from .const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEVICE_CLASS,
    CONF_SOURCE_ENTITY,
    CONF_UNIT_OF_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:table"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_SOURCE_ENTITY): cv.entity_id,
        vol.Required(CONF_ATTRIBUTE_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize attribute sensor config entry."""
    registry = er.async_get(hass)
    source = er.async_validate_entity_id(
        registry, config_entry.options[CONF_SOURCE_ENTITY]
    )
    attribute_name: str = config_entry.options[CONF_ATTRIBUTE_NAME]
    device_class: SensorDeviceClass | None = None
    if config_entry.options.get(CONF_DEVICE_CLASS) is not None:
        device_class = SensorDeviceClass(config_entry.options[CONF_DEVICE_CLASS])
    unit_of_measurement: str | None = config_entry.options.get(CONF_UNIT_OF_MEASUREMENT)

    async_add_entities(
        [
            AttributeSensor(
                source,
                config_entry.title,
                attribute_name,
                device_class,
                unit_of_measurement,
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
    """Set up the attribute sensor."""
    source: str = config[CONF_SOURCE_ENTITY]
    name: str | None = config.get(CONF_NAME)
    attribute_name: str = config[CONF_ATTRIBUTE_NAME]
    device_class: SensorDeviceClass | None = None
    if config.get(CONF_DEVICE_CLASS) is not None:
        device_class = SensorDeviceClass(config[CONF_DEVICE_CLASS])
    unit_of_measurement: str | None = config.get(CONF_UNIT_OF_MEASUREMENT)
    unique_id = config.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            AttributeSensor(
                source,
                name,
                attribute_name,
                device_class,
                unit_of_measurement,
                unique_id,
            )
        ]
    )


class AttributeSensor(SensorEntity):
    """Representation of an attribute sensor."""

    _attr_icon = ICON
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        source: str,
        name: str | None,
        attribute_name: str,
        device_class: SensorDeviceClass | None,
        unit_of_measurement: str | None,
        unique_id: str | None,
    ) -> None:
        """Initialize the attribute sensor."""
        self._attr_unique_id = unique_id
        self._state: str | None = None

        self._source = source
        self._attribute_name = attribute_name

        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement

        self._attribute_value = None

        if name:
            self._attr_name = name
        else:
            self._attr_name = f"{attribute_name} sensor".capitalize()

    async def async_added_to_hass(self) -> None:
        """Handle added to Hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source], self._async_attribute_sensor_state_listener
            )
        )

        state = self.hass.states.get(self._source)
        state_event = Event("", {"entity_id": self._source, "new_state": state})
        self._async_attribute_sensor_state_listener(state_event)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        value: StateType | datetime = self._state
        return value

    @callback
    def _async_attribute_sensor_state_listener(
        self, event: EventType, update_state: bool = True
    ) -> None:
        """Handle the source state change."""
        new_state: State | None = event.data.get("new_state")
        entity_id: str = event.data["entity_id"]

        if (
            new_state is None
            or new_state.state is None
            or new_state.state
            in [
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ]
        ):
            self._state = STATE_UNKNOWN
            if update_state:
                self.async_write_ha_state()
            return

        _LOGGER.debug("State changed for %s, updating attribute sensor", entity_id)

        if update_state:
            if self._attribute_name not in new_state.attributes:
                _LOGGER.warning(
                    'Entity "%s" does not have attribute key "%s"',
                    entity_id,
                    self._attribute_name,
                )
                return
            self._state = new_state.attributes.get(self._attribute_name)
            self.async_write_ha_state()
