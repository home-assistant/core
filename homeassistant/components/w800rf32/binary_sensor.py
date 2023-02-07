"""Support for w800rf32 binary sensors."""
from __future__ import annotations

import logging

import W800rf32 as w800
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_DEVICES, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, event as evt
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import W800RF32_DEVICE

_LOGGER = logging.getLogger(__name__)

CONF_OFF_DELAY = "off_delay"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICES): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                    vol.Optional(CONF_OFF_DELAY): vol.All(
                        cv.time_period, cv.positive_timedelta
                    ),
                }
            )
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Binary Sensor platform to w800rf32."""
    binary_sensors = []
    # device_id --> "c1 or a3" X10 device. entity (type dictionary)
    # --> name, device_class etc
    for device_id, entity in config[CONF_DEVICES].items():
        _LOGGER.debug(
            "Add %s w800rf32.binary_sensor (class %s)",
            entity[CONF_NAME],
            entity.get(CONF_DEVICE_CLASS),
        )

        device = W800rf32BinarySensor(
            device_id,
            entity.get(CONF_NAME),
            entity.get(CONF_DEVICE_CLASS),
            entity.get(CONF_OFF_DELAY),
        )

        binary_sensors.append(device)

    add_entities(binary_sensors)


class W800rf32BinarySensor(BinarySensorEntity):
    """A representation of a w800rf32 binary sensor."""

    _attr_should_poll = False

    def __init__(self, device_id, name, device_class=None, off_delay=None):
        """Initialize the w800rf32 sensor."""
        self._signal = W800RF32_DEVICE.format(device_id)
        self._name = name
        self._device_class = device_class
        self._off_delay = off_delay
        self._state = False
        self._delay_listener = None

    @callback
    def _off_delay_listener(self, now):
        """Switch device off after a delay."""
        self._delay_listener = None
        self.update_state(False)

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def device_class(self):
        """Return the sensor class."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if the sensor state is True."""
        return self._state

    @callback
    def binary_sensor_update(self, event):
        """Call for control updates from the w800rf32 gateway."""

        if not isinstance(event, w800.W800rf32Event):
            return

        dev_id = event.device
        command = event.command

        _LOGGER.debug(
            "BinarySensor update (Device ID: %s Command %s ...)", dev_id, command
        )

        # Update the w800rf32 device state
        if command in ("On", "Off"):
            is_on = command == "On"
            self.update_state(is_on)

        if self.is_on and self._off_delay is not None and self._delay_listener is None:
            self._delay_listener = evt.async_track_point_in_time(
                self.hass, self._off_delay_listener, dt_util.utcnow() + self._off_delay
            )

    def update_state(self, state):
        """Update the state of the device."""
        self._state = state
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        async_dispatcher_connect(self.hass, self._signal, self.binary_sensor_update)
