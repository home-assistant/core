"""Support for Pilight sensors."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_PAYLOAD, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import EVENT, EVENT_TYPE

_LOGGER = logging.getLogger(__name__)

CONF_VARIABLE = "variable"

DEFAULT_NAME = "Pilight Sensor"
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_VARIABLE): cv.string,
        vol.Required(CONF_PAYLOAD): vol.Schema(dict),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Pilight Sensor."""
    add_entities(
        [
            PilightSensor(
                hass=hass,
                name=config[CONF_NAME],
                variable=config[CONF_VARIABLE],
                payload=config[CONF_PAYLOAD],
                unit_of_measurement=config.get(CONF_UNIT_OF_MEASUREMENT),
            )
        ]
    )


class PilightSensor(SensorEntity):
    """Representation of a sensor that can be updated using Pilight."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        variable: str,
        payload: dict[str, Any],
        unit_of_measurement: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._attr_name = name
        self._variable = variable
        self._payload = payload
        self._attr_native_unit_of_measurement = unit_of_measurement

        hass.bus.listen(EVENT, self._handle_code)

    def _handle_code(self, call: EVENT_TYPE) -> None:
        """Handle received code by the pilight-daemon.

        If the code matches the defined payload
        of this sensor the sensor state is changed accordingly.
        """
        # Check if received code matches defined payload
        # True if payload is contained in received code dict, not
        # all items have to match
        if self._payload.items() <= call.data.items():
            try:
                value = call.data[self._variable]
                self._attr_native_value = value
                self.schedule_update_ha_state()
            except KeyError:
                _LOGGER.error(
                    "No variable %s in received code data %s",
                    str(self._variable),
                    str(call.data),
                )
