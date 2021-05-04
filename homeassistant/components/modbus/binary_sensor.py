"""Support for Modbus Coil and Discrete Input sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_COILS,
    CONF_HUB,
    CONF_INPUT_TYPE,
    CONF_INPUTS,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    MODBUS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_COILS, CONF_INPUTS),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_INPUTS): [
                vol.All(
                    cv.deprecated(CALL_TYPE_COIL, CONF_ADDRESS),
                    vol.Schema(
                        {
                            vol.Required(CONF_ADDRESS): cv.positive_int,
                            vol.Required(CONF_NAME): cv.string,
                            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                            vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
                            vol.Optional(CONF_SLAVE): cv.positive_int,
                            vol.Optional(
                                CONF_INPUT_TYPE, default=CALL_TYPE_COIL
                            ): vol.In([CALL_TYPE_COIL, CALL_TYPE_DISCRETE]),
                        }
                    ),
                )
            ]
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up the Modbus binary sensors."""
    sensors = []

    #  check for old config:
    if discovery_info is None:
        _LOGGER.warning(
            "Binary_sensor configuration is deprecated, will be removed in a future release"
        )
        discovery_info = {
            CONF_NAME: "no name",
            CONF_BINARY_SENSORS: config[CONF_INPUTS],
        }

    for entry in discovery_info[CONF_BINARY_SENSORS]:
        if CONF_HUB in entry:
            hub = hass.data[MODBUS_DOMAIN][entry[CONF_HUB]]
        else:
            hub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        if CONF_SCAN_INTERVAL not in entry:
            entry[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        sensors.append(
            ModbusBinarySensor(
                hub,
                hass,
                entry[CONF_NAME],
                entry.get(CONF_SLAVE),
                entry[CONF_ADDRESS],
                entry.get(CONF_DEVICE_CLASS),
                entry[CONF_INPUT_TYPE],
                entry[CONF_SCAN_INTERVAL],
            )
        )

    async_add_entities(sensors)


class ModbusBinarySensor(BinarySensorEntity):
    """Modbus binary sensor."""

    def __init__(
        self, hub, hass, name, slave, address, device_class, input_type, scan_interval
    ):
        """Initialize the Modbus binary sensor."""
        self._hub = hub
        self._hass = hass
        self._name = name
        self._slave = int(slave) if slave else None
        self._address = int(address)
        self._device_class = device_class
        self._input_type = input_type
        self._value = None
        self._available = True
        self._scan_interval = timedelta(seconds=scan_interval)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_track_time_interval(
            self._hass, lambda arg: self.update(), self._scan_interval
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """

        # Handle polling directly in this entity
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def update(self):
        """Update the state of the sensor."""
        if self._input_type == CALL_TYPE_COIL:
            result = self._hub.read_coils(self._slave, self._address, 1)
        else:
            result = self._hub.read_discrete_inputs(self._slave, self._address, 1)
        if result is None:
            self._available = False
            self.schedule_update_ha_state()
            return

        self._value = result.bits[0] & 1
        self._available = True
        self.schedule_update_ha_state()
