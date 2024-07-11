"""Support for MQTT room presence detection."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.json import json_loads

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE = "distance"
ATTR_ROOM = "room"

CONF_AWAY_TIMEOUT = "away_timeout"

DEFAULT_AWAY_TIMEOUT = 0
DEFAULT_NAME = "Room Sensor"
DEFAULT_TIMEOUT = 5
DEFAULT_TOPIC = "room_presence"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_AWAY_TIMEOUT, default=DEFAULT_AWAY_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
).extend(mqtt.MQTT_RO_SCHEMA.schema)


@lru_cache(maxsize=256)
def _slugify_upper(string: str) -> str:
    """Return a slugified version of string, uppercased."""
    return slugify(string).upper()


MQTT_PAYLOAD = vol.Schema(
    vol.All(
        json_loads,
        vol.Schema(
            {
                vol.Required(ATTR_ID): cv.string,
                vol.Required(ATTR_DISTANCE): vol.Coerce(float),
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT room Sensor."""
    # Make sure MQTT integration is enabled and the client is available
    # We cannot count on dependencies as the sensor platform setup
    # also will be triggered when mqtt is loading the `sensor` platform
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return
    async_add_entities(
        [
            MQTTRoomSensor(
                config.get(CONF_NAME),
                config[CONF_STATE_TOPIC],
                config[CONF_DEVICE_ID],
                config[CONF_TIMEOUT],
                config[CONF_AWAY_TIMEOUT],
                config.get(CONF_UNIQUE_ID),
            )
        ]
    )


class MQTTRoomSensor(SensorEntity):
    """Representation of a room sensor that is updated via MQTT."""

    def __init__(
        self,
        name: str | None,
        state_topic: str,
        device_id: str,
        timeout: int,
        consider_home: int,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = unique_id

        self._state = STATE_NOT_HOME
        self._name = name
        self._state_topic = f"{state_topic}/+"
        self._device_id = _slugify_upper(device_id)
        self._timeout = timeout
        self._consider_home = (
            timedelta(seconds=consider_home) if consider_home else None
        )
        self._distance = None
        self._updated = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def update_state(device_id, room, distance):
            """Update the sensor state."""
            self._state = room
            self._distance = distance
            self._updated = dt_util.utcnow()

            self.async_write_ha_state()

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                data = MQTT_PAYLOAD(msg.payload)
            except vol.MultipleInvalid as error:
                _LOGGER.debug("Skipping update because of malformatted data: %s", error)
                return

            device = _parse_update_data(msg.topic, data)
            if device.get(CONF_DEVICE_ID) == self._device_id:
                if self._distance is None or self._updated is None:
                    update_state(**device)
                else:
                    # update if:
                    # device is in the same room OR
                    # device is closer to another room OR
                    # last update from other room was too long ago
                    timediff = dt_util.utcnow() - self._updated
                    if (
                        device.get(ATTR_ROOM) == self._state
                        or device.get(ATTR_DISTANCE) < self._distance
                        or timediff.total_seconds() >= self._timeout
                    ):
                        update_state(**device)

        await mqtt.async_subscribe(self.hass, self._state_topic, message_received, 1)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_DISTANCE: self._distance}

    @property
    def native_value(self):
        """Return the current room of the entity."""
        return self._state

    def update(self) -> None:
        """Update the state for absent devices."""
        if (
            self._updated
            and self._consider_home
            and dt_util.utcnow() - self._updated > self._consider_home
        ):
            self._state = STATE_NOT_HOME


def _parse_update_data(topic: str, data: dict[str, Any]) -> dict[str, Any]:
    """Parse the room presence update."""
    parts = topic.split("/")
    room = parts[-1]
    device_id = _slugify_upper(data.get(ATTR_ID))
    distance = data.get("distance")
    return {ATTR_DEVICE_ID: device_id, ATTR_ROOM: room, ATTR_DISTANCE: distance}
