"""Use multiple sensors to control a binary sensor."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.event as eventHelper

from .const import (
    CONF_ACTIVE_STATES,
    CONF_ENTITIES_KEEP,
    CONF_ENTITIES_TOGGLE,
    CONF_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Required(CONF_ENTITIES_TOGGLE, default=[]): cv.ensure_list,
        vol.Required(CONF_ENTITIES_KEEP, default=[]): cv.ensure_list,
        vol.Optional(
            CONF_ACTIVE_STATES, default='["on", "occupied", 1, True, "active"]'
        ): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup room occupancy entities."""  # noqa: D401
    name = config.get(CONF_NAME)
    timeout = config.get(CONF_TIMEOUT)
    entities_toggle = config.get(CONF_ENTITIES_TOGGLE)
    entities_keep = config.get(CONF_ENTITIES_KEEP)
    active_states = config.get(CONF_ACTIVE_STATES)

    _LOGGER.debug("binary_sensor.py setup_platform triggered!")
    _LOGGER.debug(
        "name: %s, timeout %i, entities_toggle %s, entities_keep %s, active_states %s",
        name,
        timeout,
        entities_toggle,
        entities_keep,
        active_states,
    )
    await async_add_entities(
        [
            RoomOccupancyBinarySensor(
                hass,
                config,
            )
        ]
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Add entity."""
    _LOGGER.debug("binary_sensor.py async_setup_entry triggered!")
    data = entry.as_dict()["data"]
    name = data[CONF_NAME]
    timeout = data[CONF_TIMEOUT]
    entities_toggle = data[CONF_ENTITIES_TOGGLE]
    entities_keep = data[CONF_ENTITIES_KEEP]
    active_states = data[CONF_ACTIVE_STATES]
    _LOGGER.debug(
        "name: %s, timeout %i, entities_toggle %s, entities_keep %s, active_states %s",
        name,
        timeout,
        entities_toggle,
        entities_keep,
        active_states,
    )
    async_add_entities(
        [
            RoomOccupancyBinarySensor(
                hass,
                entry,
            )
        ]
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("binary_sensor.py async_unload_entry triggered!")
    data = entry.as_dict()["data"]
    _LOGGER.debug("entry_id is: %s", data)
    unload_ok = True
    if unload_ok:
        # await self.hass.config_entries.async_forward_entry_unload(
        await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
        hass.data[DOMAIN].pop(data["entry_id"])

    return unload_ok


class RoomOccupancyBinarySensor(BinarySensorEntity):
    """Class for Room Occupancy."""

    def __init__(self, hass, config):
        """Init."""
        _LOGGER.debug(
            "binary_sensor.py __init__ triggered! config: %s", config.as_dict()
        )
        data = config.as_dict()["data"]
        _LOGGER.debug(data)
        self.hass = hass
        self.attr = {
            CONF_TIMEOUT: data[CONF_TIMEOUT],
            CONF_ENTITIES_TOGGLE: data[CONF_ENTITIES_TOGGLE],
            CONF_ENTITIES_KEEP: data[CONF_ENTITIES_KEEP],
            CONF_ACTIVE_STATES: data[CONF_ACTIVE_STATES],
        }
        self._state = STATE_OFF
        self._name = data[CONF_NAME]
        _LOGGER.debug(
            "name: %s, entities_toggle: %s, entities_keep: %s, timeout: %i, state: %s, active_states: %s",
            self._name,
            self.attr[CONF_ENTITIES_TOGGLE],
            self.attr[CONF_ENTITIES_KEEP],
            self.attr[CONF_TIMEOUT],
            self._state,
            self.attr[CONF_ACTIVE_STATES],
        )

        eventHelper.async_track_state_change(
            self.hass,
            self.attr[CONF_ENTITIES_TOGGLE] + self.attr[CONF_ENTITIES_KEEP],
            self.entity_state_changed,
        )

    def entity_state_changed(self, entity_id, old_state, new_state):
        """Trigger the update function on change of an entity."""
        _LOGGER.debug("entity_state_changed triggered! entity: %s", entity_id)
        self.update()

    def update(self):
        """Update the state of the binary sensor."""
        # if state is false, check all entities
        _LOGGER.debug("update triggered for %s!", self.entity_id)
        found = False

        if self._state == STATE_ON:
            use_entities = (
                self.attr[CONF_ENTITIES_TOGGLE] + self.attr[CONF_ENTITIES_KEEP]
            )
        else:
            use_entities = self.attr[CONF_ENTITIES_TOGGLE]
        _LOGGER.debug("checking the following entities: %s", use_entities)
        _LOGGER.debug(
            "the following states are considered true: %s",
            self.attr[CONF_ACTIVE_STATES],
        )
        for entity in use_entities:
            _LOGGER.debug("checking entity %s", entity)
            state = self.hass.states.get(entity).state
            _LOGGER.debug("state is: %s", state)
            if state in self.attr[CONF_ACTIVE_STATES]:
                _LOGGER.debug("entity is active!")
                found = True
            else:
                _LOGGER.debug("entity is inactive!")
        if found:
            self._state = STATE_ON
            # self.hass.state.set()
        else:
            self._state = STATE_OFF
        _LOGGER.debug("finished setting state, _state is: %s", self._state)
        self.hass.states.set("binary_sensor." + self._name, self._state, self.attr)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return BinarySensorDeviceClass.OCCUPANCY
