"""Support for collecting data from the ARWN project."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import DEGREE, UnitOfPrecipitationDepth, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
from homeassistant.util.json import json_loads_object

_LOGGER = logging.getLogger(__name__)

DOMAIN = "arwn"

DATA_ARWN = "arwn"
TOPIC = "arwn/#"


def discover_sensors(topic, payload):
    """Given a topic, dynamically create the right sensor type.

    Async friendly.
    """
    parts = topic.split("/")
    unit = payload.get("units", "")
    domain = parts[1]
    if domain == "temperature":
        name = parts[2]
        if unit == "F":
            unit = UnitOfTemperature.FAHRENHEIT
        else:
            unit = UnitOfTemperature.CELSIUS
        return ArwnSensor(
            topic, name, "temp", unit, device_class=SensorDeviceClass.TEMPERATURE
        )
    if domain == "moisture":
        name = f"{parts[2]} Moisture"
        return ArwnSensor(topic, name, "moisture", unit, "mdi:water-percent")
    if domain == "rain":
        if len(parts) >= 3 and parts[2] == "today":
            return ArwnSensor(
                topic,
                "Rain Since Midnight",
                "since_midnight",
                UnitOfPrecipitationDepth.INCHES,
                device_class=SensorDeviceClass.PRECIPITATION,
            )
        return (
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
        )
    if domain == "barometer":
        return ArwnSensor(topic, "Barometer", "pressure", unit, "mdi:thermometer-lines")
    if domain == "wind":
        return (
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
                topic + "/dir", "Wind Direction", "direction", DEGREE, "mdi:compass"
            ),
        )


def _slug(name):
    return f"sensor.arwn_{slugify(name)}"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ARWN platform."""

    @callback
    def async_sensor_event_received(msg: mqtt.ReceiveMessage) -> None:
        """Process events as sensors.

        When a new event on our topic (arwn/#) is received we map it
        into a known kind of sensor based on topic name. If we've
        never seen this before, we keep this sensor around in a global
        cache. If we have seen it before, we update the values of the
        existing sensor. Either way, we push an ha state update at the
        end for the new event we've seen.

        This lets us dynamically incorporate sensors without any
        configuration on our side.
        """
        event = json_loads_object(msg.payload)
        sensors = discover_sensors(msg.topic, event)
        if not sensors:
            return

        if (store := hass.data.get(DATA_ARWN)) is None:
            store = hass.data[DATA_ARWN] = {}

        if isinstance(sensors, ArwnSensor):
            sensors = (sensors,)

        if "timestamp" in event:
            del event["timestamp"]

        for sensor in sensors:
            if sensor.name not in store:
                sensor.hass = hass
                sensor.set_event(event)
                store[sensor.name] = sensor
                _LOGGER.debug(
                    "Registering sensor %(name)s => %(event)s",
                    {"name": sensor.name, "event": event},
                )
                async_add_entities((sensor,), True)
            else:
                _LOGGER.debug(
                    "Recording sensor %(name)s => %(event)s",
                    {"name": sensor.name, "event": event},
                )
                store[sensor.name].set_event(event)

    await mqtt.async_subscribe(hass, TOPIC, async_sensor_event_received, 0)


class ArwnSensor(SensorEntity):
    """Representation of an ARWN sensor."""

    _attr_should_poll = False

    def __init__(self, topic, name, state_key, units, icon=None, device_class=None):
        """Initialize the sensor."""
        self.entity_id = _slug(name)
        self._attr_name = name
        # This mqtt topic for the sensor which is its uid
        self._attr_unique_id = topic
        self._state_key = state_key
        self._attr_native_unit_of_measurement = units
        self._attr_icon = icon
        self._attr_device_class = device_class

    def set_event(self, event):
        """Update the sensor with the most recent event."""
        ev = {}
        ev.update(event)
        self._attr_extra_state_attributes = ev
        self._attr_native_value = ev.get(self._state_key, None)
        self.async_write_ha_state()
