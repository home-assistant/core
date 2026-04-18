"""Support for Pilight binary sensors."""

from __future__ import annotations

import datetime
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import track_point_in_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import EVENT, EVENT_TYPE

CONF_VARIABLE = "variable"
CONF_RESET_DELAY_SEC = "reset_delay_sec"

DEFAULT_NAME = "Pilight Binary Sensor"
PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_VARIABLE): cv.string,
        vol.Required(CONF_PAYLOAD): vol.Schema(dict),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default="on"): vol.Any(
            cv.positive_int, cv.small_float, cv.string
        ),
        vol.Optional(CONF_PAYLOAD_OFF, default="off"): vol.Any(
            cv.positive_int, cv.small_float, cv.string
        ),
        vol.Optional(CONF_DISARM_AFTER_TRIGGER, default=False): cv.boolean,
        vol.Optional(CONF_RESET_DELAY_SEC, default=30): cv.positive_int,
    }
)

type _PAYLOAD_SET_TYPE = str | int | float


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Pilight Binary Sensor."""
    if config.get(CONF_DISARM_AFTER_TRIGGER):
        add_entities(
            [
                PilightTriggerSensor(
                    hass=hass,
                    name=config[CONF_NAME],
                    variable=config[CONF_VARIABLE],
                    payload=config[CONF_PAYLOAD],
                    on_value=config[CONF_PAYLOAD_ON],
                    off_value=config[CONF_PAYLOAD_OFF],
                    rst_dly_sec=config[CONF_RESET_DELAY_SEC],
                )
            ]
        )
    else:
        add_entities(
            [
                PilightBinarySensor(
                    hass=hass,
                    name=config[CONF_NAME],
                    variable=config[CONF_VARIABLE],
                    payload=config[CONF_PAYLOAD],
                    on_value=config[CONF_PAYLOAD_ON],
                    off_value=config[CONF_PAYLOAD_OFF],
                )
            ]
        )


class PilightBinarySensor(BinarySensorEntity):
    """Representation of a binary sensor that can be updated using Pilight."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        variable: str,
        payload: dict[str, Any],
        on_value: _PAYLOAD_SET_TYPE,
        off_value: _PAYLOAD_SET_TYPE,
    ) -> None:
        """Initialize the sensor."""
        self._attr_is_on = False
        self._hass = hass
        self._attr_name = name
        self._variable = variable
        self._payload = payload
        self._on_value = on_value
        self._off_value = off_value

        hass.bus.listen(EVENT, self._handle_code)

    def _handle_code(self, call: EVENT_TYPE) -> None:
        """Handle received code by the pilight-daemon.

        If the code matches the defined payload
        of this sensor the sensor state is changed accordingly.
        """
        # Check if received code matches defined playoad
        # True if payload is contained in received code dict
        payload_ok = True
        for key in self._payload:
            if key not in call.data:
                payload_ok = False
                continue
            if self._payload[key] != call.data[key]:
                payload_ok = False
        # Read out variable if payload ok
        if payload_ok:
            if self._variable not in call.data:
                return
            value = call.data[self._variable]
            self._attr_is_on = value == self._on_value
            self.schedule_update_ha_state()


class PilightTriggerSensor(BinarySensorEntity):
    """Representation of a binary sensor that can be updated using Pilight."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        variable: str,
        payload: dict[str, Any],
        on_value: _PAYLOAD_SET_TYPE,
        off_value: _PAYLOAD_SET_TYPE,
        rst_dly_sec: int,
    ) -> None:
        """Initialize the sensor."""
        self._attr_is_on = False
        self._hass = hass
        self._attr_name = name
        self._variable = variable
        self._payload = payload
        self._on_value = on_value
        self._off_value = off_value
        self._reset_delay_sec = rst_dly_sec
        self._delay_after: datetime.datetime | None = None
        self._hass = hass

        hass.bus.listen(EVENT, self._handle_code)

    def _reset_state(self, _: datetime.datetime) -> None:
        self._attr_is_on = False
        self._delay_after = None
        self.schedule_update_ha_state()

    def _handle_code(self, call: EVENT_TYPE) -> None:
        """Handle received code by the pilight-daemon.

        If the code matches the defined payload
        of this sensor the sensor state is changed accordingly.
        """
        # Check if received code matches defined payload
        # True if payload is contained in received code dict
        payload_ok = True
        for key in self._payload:
            if key not in call.data:
                payload_ok = False
                continue
            if self._payload[key] != call.data[key]:
                payload_ok = False
        # Read out variable if payload ok
        if payload_ok:
            if self._variable not in call.data:
                return
            value = call.data[self._variable]
            self._attr_is_on = value == self._on_value
            if self._delay_after is None:
                self._delay_after = dt_util.utcnow() + datetime.timedelta(
                    seconds=self._reset_delay_sec
                )
                track_point_in_time(self._hass, self._reset_state, self._delay_after)
            self.schedule_update_ha_state()
