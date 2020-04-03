"""Support for collecting data from the ARWN project."""
import json
import logging

from homeassistant.components import mqtt
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

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
            unit = TEMP_FAHRENHEIT
        else:
            unit = TEMP_CELSIUS
        return ArwnSensor(name, "temp", unit)
    if domain == "moisture":
        name = parts[2] + " Moisture"
        return ArwnSensor(name, "moisture", unit, "mdi:water-percent")
    if domain == "rain":
        if len(parts) >= 3 and parts[2] == "today":
            return ArwnSensor(
                "Rain Since Midnight", "since_midnight", "in", "mdi:water"
            )
    if domain == "barometer":
        return ArwnSensor("Barometer", "pressure", unit, "mdi:thermometer-lines")
    if domain == "wind":
        return (
            ArwnSensor("Wind Speed", "speed", unit, "mdi:speedometer"),
            ArwnSensor("Wind Gust", "gust", unit, "mdi:speedometer"),
            ArwnSensor("Wind Direction", "direction", "°", "mdi:compass"),
        )


def _slug(name):
    return f"sensor.arwn_{slugify(name)}"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the ARWN platform."""

    @callback
    def async_sensor_event_received(msg):
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
        event = json.loads(msg.payload)
        sensors = discover_sensors(msg.topic, event)
        if not sensors:
            return

        store = hass.data.get(DATA_ARWN)
        if store is None:
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
                    "Registering new sensor %(name)s => %(event)s",
                    dict(name=sensor.name, event=event),
                )
                async_add_entities((sensor,), True)
            else:
                store[sensor.name].set_event(event)

    await mqtt.async_subscribe(hass, TOPIC, async_sensor_event_received, 0)
    return True


class ArwnSensor(Entity):
    """Representation of an ARWN sensor."""

    def __init__(self, name, state_key, units, icon=None):
        """Initialize the sensor."""
        self.hass = None
        self.entity_id = _slug(name)
        self._name = name
        self._state_key = state_key
        self.event = {}
        self._unit_of_measurement = units
        self._icon = icon

    def set_event(self, event):
        """Update the sensor with the most recent event."""
        self.event = {}
        self.event.update(event)
        self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the device."""
        return self.event.get(self._state_key, None)

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def state_attributes(self):
        """Return all the state attributes."""
        return self.event

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the state is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        return self._icon
