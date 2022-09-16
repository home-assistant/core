"""Support for MQTT room presence detection."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
from typing import TypedDict

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TIMEOUT,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt, slugify

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE = "distance"
ATTR_ROOM = "room"
ATTR_UPDATED = "updated"
ATTR_EXTRA_ROOMS = "extra_rooms"

CONF_AWAY_TIMEOUT = "away_timeout"
CONF_EXTRA_ROOMS = "extra_rooms"

DEFAULT_AWAY_TIMEOUT = 0
DEFAULT_NAME = "Room Sensor"
DEFAULT_TIMEOUT = 5
DEFAULT_TOPIC = "room_presence"
DEFAULT_EXTRA_ROOMS = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_AWAY_TIMEOUT, default=DEFAULT_AWAY_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_EXTRA_ROOMS, default=DEFAULT_EXTRA_ROOMS): cv.positive_int,
    }
).extend(mqtt.config.MQTT_RO_SCHEMA.schema)

MQTT_PAYLOAD = vol.Schema(
    vol.All(
        json.loads,
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
    async_add_entities(
        [
            MQTTRoomSensor(
                config.get(CONF_NAME),
                config.get(CONF_STATE_TOPIC),
                config.get(CONF_DEVICE_ID),
                config.get(CONF_TIMEOUT),
                config.get(CONF_AWAY_TIMEOUT),
                config.get(CONF_EXTRA_ROOMS),
            )
        ]
    )


class MQTTRoomState(TypedDict):
    """Hold the state of a room."""

    room: str
    distance: float
    updated: datetime


class MQTTRoomSensor(SensorEntity):
    """Representation of a room sensor that is updated via MQTT."""

    def __init__(
        self, name, state_topic, device_id, timeout, consider_home, extra_rooms
    ):
        """Initialize the sensor."""
        self._name = name
        self._state_topic = f"{state_topic}/+"
        self._device_id = slugify(device_id).upper()
        self._timeout = timeout
        self._consider_home = (
            timedelta(seconds=consider_home) if consider_home else None
        )
        self._room_states: list[MQTTRoomState] = [
            MQTTRoomState(room=STATE_NOT_HOME, distance=None, updated=None),
        ]

        for _ in range(extra_rooms):
            self._room_states.append(
                MQTTRoomState(room=STATE_NOT_HOME, distance=None, updated=None)
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def update_state(record, device_id, room, distance):
            """Update the sensor state."""

            record.update(room=room, distance=distance, updated=dt.utcnow())

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
                for rec in self._room_states:
                    if rec["distance"] is None or rec["updated"] is None:
                        update_state(rec, **device)
                        break

                    # update if:
                    # device is in the same room OR
                    # device is closer to another room OR
                    # last update from other room was too long ago
                    timediff = dt.utcnow() - rec["updated"]
                    if (
                        device.get(ATTR_ROOM) == rec["room"]
                        or device.get(ATTR_DISTANCE) < rec["distance"]
                        or timediff.total_seconds() >= self._timeout
                    ):
                        update_state(rec, **device)
                        break

        await mqtt.async_subscribe(self.hass, self._state_topic, message_received, 1)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        primary_room_state = self._room_states[0]
        attributes = {
            ATTR_DISTANCE: primary_room_state["distance"],
            ATTR_EXTRA_ROOMS: {},
        }
        for rec in self._room_states[1:]:
            attributes[ATTR_EXTRA_ROOMS][rec["room"]] = rec["distance"]
        return attributes

    @property
    def native_value(self) -> str:
        """Return the current room of the entity."""
        primary_room_state = self._room_states[0]
        return primary_room_state["room"]

    def update(self) -> None:
        """Update the state for absent devices."""
        primary_room_state = self._room_states[0]
        updated = primary_room_state["updated"]
        if (
            updated
            and self._consider_home
            and dt.utcnow() - updated > self._consider_home
        ):
            primary_room_state["room"] = STATE_NOT_HOME


def _parse_update_data(topic, data):
    """Parse the room presence update."""
    parts = topic.split("/")
    room = parts[-1]
    device_id = slugify(data.get(ATTR_ID)).upper()
    distance = data.get("distance")
    parsed_data = {ATTR_DEVICE_ID: device_id, ATTR_ROOM: room, ATTR_DISTANCE: distance}
    return parsed_data
