"""Support for Modbus Coil and Discrete Input sensors."""
from __future__ import annotations

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
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .base_platform import BasePlatform
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

PARALLEL_UPDATES = 1
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
        sensors.append(ModbusBinarySensor(hub, entry))

    async_add_entities(sensors)


class ModbusBinarySensor(BasePlatform, RestoreEntity, BinarySensorEntity):
    """Modbus binary sensor."""

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._value = state.state == STATE_ON
        else:
            self._value = None

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._value

    async def async_update(self, now=None):
        """Update the state of the sensor."""
        result = await self._hub.async_pymodbus_call(
            self._slave, self._address, 1, self._input_type
        )
        if result is None:
            self._available = False
            self.async_write_ha_state()
            return

        self._value = result.bits[0] & 1
        self._available = True
        self.async_write_ha_state()
