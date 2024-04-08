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
    _LOGGER.debug("entry: %s", entry.as_dict())
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
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, hass: HomeAssistant, config) -> None:
        """Init."""
        _LOGGER.debug("Init triggered, config: %s", config.as_dict())
        data = config.as_dict()["data"]
        _LOGGER.debug("data: %s", data)
        self.hass = hass
        _LOGGER.debug("hass: %s", hass)
        self.attr = {
            CONF_TIMEOUT: data[CONF_TIMEOUT],
            CONF_ENTITIES_TOGGLE: data[CONF_ENTITIES_TOGGLE],
            CONF_ENTITIES_KEEP: data[CONF_ENTITIES_KEEP],
            CONF_ACTIVE_STATES: data[CONF_ACTIVE_STATES],
            "device_class": BinarySensorDeviceClass.OCCUPANCY,
            "friendly_name": data[CONF_NAME],
        }
        _LOGGER.debug("attr: %s", self.attr)
        self._state = STATE_OFF
        _LOGGER.debug("state: %s", self._state)
        self._name = data[CONF_NAME]
        _LOGGER.debug("name: %s", self._name)
        self._timeout_handle: Optional[Callable[[], None]] = None
        self.entity_id = (
            "binary_sensor." + self._name.lower().replace(" ", "_") + "_occupancy"
        )
        _LOGGER.debug("entity_id: %s", self.entity_id)
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
        _LOGGER.debug("device_class: %s", self._attr_device_class)
        _LOGGER.debug("self: %s", self)

        eventHelper.async_track_state_change(
            self.hass,
            self.attr[CONF_ENTITIES_TOGGLE] + self.attr[CONF_ENTITIES_KEEP],
            self.async_update,
        )

    async def async_update(self, entity=None, old_state=None, new_state=None) -> None:
        """Fetch new state data for the sensor."""
        _LOGGER.debug("update triggered for %s!", self.entity_id)
        found = self.check_states()
        if found:
            self._state = STATE_ON
            self.hass.states.async_set(
                entity_id=self.entity_id,
                new_state=self._state,
                attributes=self.attr,
            )
            if self._timeout_handle is not None:
                _LOGGER.debug("cancelling previous timeout: %s", self._timeout_handle)
                self._timeout_handle()
                _LOGGER.debug(
                    "cancelling previous timeout done: %s", self._timeout_handle
                )
        elif self._state != STATE_OFF:
            _LOGGER.debug("state is off, setting a timeout")
            self._timeout_handle = eventHelper.async_call_later(
                self.hass, self.attr[CONF_TIMEOUT], self.timeout_func
            )
            _LOGGER.debug("timeout set: %s", self._timeout_handle)

    async def timeout_func(self, *args) -> None:
        """Set the state to off after the timeout."""
        _LOGGER.debug("timeout reached, setting state to off")
        self._state = STATE_OFF
        self.hass.states.async_set(
            entity_id=self.entity_id,
            new_state=self._state,
            attributes=self.attr,
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
        _LOGGER.debug("name triggered, returned %s", self._name)
        return self._name

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class of the sensor."""
        return BinarySensorDeviceClass.OCCUPANCY

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.entity_id}P"
