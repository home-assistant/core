"""Support for room occupancy binary sensors."""
from collections.abc import Callable
import logging
from typing import Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.event as eventHelper

from .const import (
    CONF_ACTIVE_STATES,
    CONF_ENTITIES_KEEP,
    CONF_ENTITIES_TOGGLE,
    CONF_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add entity."""
    _LOGGER.debug("binary_sensor.py async_setup_entry triggered!")
    async_add_entities(
        [
            RoomOccupancyBinarySensor(
                hass,
                entry,
            )
        ]
    )


class RoomOccupancyBinarySensor(BinarySensorEntity):
    """Representation of a room occupancy binary sensor."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, config) -> None:
        """Init."""
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
        self._timeout_handle: Optional[Callable[[], None]] = None

        eventHelper.async_track_state_change(
            self.hass,
            self.attr[CONF_ENTITIES_TOGGLE] + self.attr[CONF_ENTITIES_KEEP],
            self.async_update,
        )

    async def async_update(self, entity, old_state, new_state) -> None:
        """Fetch new state data for the sensor."""
        _LOGGER.debug("update triggered for %s!", self.entity_id)
        found = self.check_states()
        if found:
            # if self._state != STATE_ON:
            self._state = STATE_ON
            self.hass.states.async_set(
                "binary_sensor." + self._name, self._state, self.attr
            )
            # Cancel the previous timeout if it exists
            if self._timeout_handle is not None:
                _LOGGER.debug("cancelling previous timeout: %s", self._timeout_handle)
                self._timeout_handle()
                _LOGGER.debug(
                    "cancelling previous timeout done: %s", self._timeout_handle
                )
        elif self._state != STATE_OFF:
            _LOGGER.debug("state is off, setting a timeout")
            # Set a new timeout
            self._timeout_handle = eventHelper.async_call_later(
                self.hass, self.attr[CONF_TIMEOUT], self.timeout_func
            )
            _LOGGER.debug("timeout set: %s", self._timeout_handle)

    async def timeout_func(self, *args):
        """Set the state to off after the timeout."""
        _LOGGER.debug("timeout reached, setting state to off")
        self._state = STATE_OFF
        self.hass.states.async_set(
            "binary_sensor." + self._name, self._state, self.attr
        )
        self._timeout_handle = None

    def check_states(self) -> bool:
        """Check state of all entities."""
        found = False
        if self._state == STATE_ON:
            use_entities = (
                self.attr[CONF_ENTITIES_TOGGLE] + self.attr[CONF_ENTITIES_KEEP]
            )
        else:
            use_entities = self.attr[CONF_ENTITIES_TOGGLE]
        for entity in use_entities:
            state = self.hass.states.get(entity)
            if state is not None and state.state in self.attr[CONF_ACTIVE_STATES]:
                found = True
        return found

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        _LOGGER.debug("is_on triggered, returned %s", self._state)
        return bool(self._state)

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class of the sensor."""
        return BinarySensorDeviceClass.OCCUPANCY
