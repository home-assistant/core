"""Support for collecting data from the ARWN project."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import DEGREE, UnitOfPrecipitationDepth, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads_object

if TYPE_CHECKING:
    from . import ArwnConfigEntry

_LOGGER = logging.getLogger(__name__)

TOPIC = "arwn/#"


def discover_sensors(topic: str, payload: dict[str, Any]) -> list[ArwnSensor] | None:
    """Given a topic, dynamically create the right sensor type.

    Async friendly.
    """
    parts = topic.split("/")
    if len(parts) < 2:
        return None
    unit = payload.get("units", "")
    domain = parts[1]
    if domain == "temperature":
        if len(parts) < 3:
            return None
        name = parts[2]
        if unit == "F":
            unit = UnitOfTemperature.FAHRENHEIT
        else:
            unit = UnitOfTemperature.CELSIUS
        return [
            ArwnSensor(
                topic, name, "temp", unit, device_class=SensorDeviceClass.TEMPERATURE
            )
        ]
    if domain == "moisture":
        if len(parts) < 3:
            return None
        name = f"{parts[2]} Moisture"
        return [ArwnSensor(topic, name, "moisture", unit, "mdi:water-percent")]
    if domain == "rain":
        if len(parts) >= 3 and parts[2] == "today":
            return [
                ArwnSensor(
                    topic,
                    "Rain Since Midnight",
                    "since_midnight",
                    UnitOfPrecipitationDepth.INCHES,
                    device_class=SensorDeviceClass.PRECIPITATION,
                )
            ]
        return [
            ArwnSensor(
                topic + "/total",
                "Total Rainfall",
                "total",
                unit,
                device_class=SensorDeviceClass.PRECIPITATION,
            ),
            ArwnSensor(
                topic + "/rate",
                "Rainfall Rate",
                "rate",
                unit,
                device_class=SensorDeviceClass.PRECIPITATION,
            ),
        ]
    if domain == "barometer":
        return [
            ArwnSensor(topic, "Barometer", "pressure", unit, "mdi:thermometer-lines")
        ]
    if domain == "wind":
        return [
            ArwnSensor(
                topic + "/speed",
                "Wind Speed",
                "speed",
                unit,
                device_class=SensorDeviceClass.WIND_SPEED,
            ),
            ArwnSensor(
                topic + "/gust",
                "Wind Gust",
                "gust",
                unit,
                device_class=SensorDeviceClass.WIND_SPEED,
            ),
            ArwnSensor(
                topic + "/dir",
                "Wind Direction",
                "direction",
                DEGREE,
                "mdi:compass",
                device_class=SensorDeviceClass.WIND_DIRECTION,
                state_class=SensorStateClass.MEASUREMENT_ANGLE,
            ),
        ]
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArwnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ARWN sensor platform."""

    @callback
    def async_sensor_event_received(msg: mqtt.ReceiveMessage) -> None:
        """Process MQTT events as sensors.

        When a new event on our topic (arwn/#) is received we map it
        into a known kind of sensor based on topic name. If we've
        never seen this before, we keep this sensor around in a global
        cache. If we have seen it before, we update the values of the
        existing sensor. Either way, we push an ha state update at the
        end for the new event we've seen.

        This lets us dynamically incorporate sensors without any
        configuration on our side.
        """
        try:
            event = json_loads_object(msg.payload)
        except ValueError:
            _LOGGER.warning(
                "Invalid JSON in MQTT message on %s: %s", msg.topic, msg.payload
            )
            return

        sensors = discover_sensors(msg.topic, event)
        if not sensors:
            return

        store = entry.runtime_data

        if "timestamp" in event:
            del event["timestamp"]

        for sensor in sensors:
            if (unique_id := sensor.unique_id) is None:
                continue
            if unique_id not in store:
                store[unique_id] = sensor
                sensor.set_initial_event(event)
                _LOGGER.debug(
                    "Registering sensor %(name)s => %(event)s",
                    {"name": sensor.name, "event": event},
                )
                async_add_entities((sensor,), False)
            else:
                _LOGGER.debug(
                    "Recording sensor %(name)s => %(event)s",
                    {"name": sensor.name, "event": event},
                )
                store[unique_id].set_event(event)

    entry.async_on_unload(
        await mqtt.async_subscribe(hass, TOPIC, async_sensor_event_received, 0)
    )


class ArwnSensor(SensorEntity):
    """Representation of an ARWN sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        topic: str,
        name: str,
        state_key: str,
        units: str,
        icon: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        # This mqtt topic for the sensor which is its uid
        self._attr_unique_id = topic
        self._state_key = state_key
        self._attr_native_unit_of_measurement = units
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    def set_initial_event(self, event: dict[str, Any]) -> None:
        """Set the initial state before the entity is registered."""
        ev: dict[str, Any] = dict(event)
        self._attr_extra_state_attributes = ev
        self._attr_native_value = ev.get(self._state_key)

    def set_event(self, event: dict[str, Any]) -> None:
        """Update the sensor with the most recent event."""
        ev: dict[str, Any] = dict(event)
        self._attr_extra_state_attributes = ev
        self._attr_native_value = ev.get(self._state_key)
        self.async_write_ha_state()
