"""Support for displaying attributes as Sensor."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PLATFORMS
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    attribute = config_entry.options[CONF_ATTRIBUTE]
    icon = config_entry.options.get(CONF_ICON)
    device_class = config_entry.options.get(CONF_DEVICE_CLASS)
    state_class = config_entry.options.get(CONF_STATE_CLASS)
    uom = config_entry.options.get(CONF_UNIT_OF_MEASUREMENT)

    async_add_entities(
        [
            AttributeSensor(
                entity_id,
                attribute,
                icon,
                device_class,
                state_class,
                uom,
                config_entry.title,
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
    """Set up the sensor."""
    entity_id: str = config[CONF_ENTITY_ID]
    name: str = config[CONF_NAME]
    attribute: str = config[CONF_ATTRIBUTE]
    unique_id: str | None = config.get(CONF_UNIQUE_ID)
    icon: str | None = config.get(CONF_ICON)
    device_class: str | None = config.get(CONF_DEVICE_CLASS)
    state_class: str | None = config.get(CONF_STATE_CLASS)
    uom: str | None = config.get(CONF_UNIT_OF_MEASUREMENT)

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    async_add_entities(
        [
            AttributeSensor(
                entity_id,
                attribute.lower(),
                icon,
                device_class,
                state_class,
                uom,
                name,
                unique_id,
            )
        ]
    )


class AttributeSensor(SensorEntity):
    """Representation of an Attribute as Sensor sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        entity_id: str,
        attribute: str,
        icon: str | None,
        device_class: str | None,
        state_class: str | None,
        uom: str | None,
        name: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = unique_id
        self._entity_id = entity_id
        self._attribute = attribute
        self._attr_name = name

        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = uom
        self._attr_state_class = state_class

    async def async_added_to_hass(self) -> None:
        """Handle added to Hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_id, self._async_attribute_sensor_state_listener
            )
        )

        # Replay current state of source entities
        state = self.hass.states.get(self._entity_id)
        state_event = Event("", {"entity_id": self._entity_id, "new_state": state})
        self._async_attribute_sensor_state_listener(state_event, update_state=False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        return {ATTR_ENTITY_ID: self._entity_id}

    @callback
    def _async_attribute_sensor_state_listener(
        self, event: Event, update_state: bool = True
    ) -> None:
        """Handle the sensor state changes."""
        new_state: State | None = event.data.get("new_state")
        # entity: str | None = event.data["entity_id"]

        if (
            new_state is None
            or new_state.state is None
            or new_state.state == STATE_UNAVAILABLE
        ):
            self._attr_native_value = STATE_UNKNOWN
            if not update_state:
                return

        self._attr_native_value = STATE_UNKNOWN

        if (
            new_state
            and new_state.attributes
            and (value := new_state.attributes.get(self._attribute))
        ):
            self._attr_native_value = value

        self.async_write_ha_state()
        return
