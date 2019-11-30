"""Support for Tado sensors for each zone."""
import logging

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import (
    DOMAIN,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
    TYPE_HOT_WATER,
)

_LOGGER = logging.getLogger(__name__)

ZONE_SENSORS = {
    TYPE_HEATING: [
        "temperature",
        "humidity",
        "power",
        "link",
        "heating",
        "tado mode",
        "overlay",
        "early start",
    ],
    TYPE_AIR_CONDITIONING: [
        "temperature",
        "humidity",
        "power",
        "link",
        "ac",
        "tado mode",
        "overlay",
    ],
    TYPE_HOT_WATER: ["power", "link", "tado mode", "overlay"],
}

DEVICE_SENSORS = ["tado bridge status"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    tado = hass.data[DOMAIN]

    try:
        zones = tado.get_zones()
    except RuntimeError:
        _LOGGER.error("Unable to get zone info")
        return

    # Create zone sensors
    sensor_items = []
    for zone in zones:
        sensor_items.extend(
            [
                create_zone_sensor(tado, zone["name"], zone["id"], variable)
                for variable in ZONE_SENSORS.get(zone["type"])
            ]
        )

    # Create device sensors
    home = tado.get_me()["homes"][0]
    sensor_items.extend(
        [
            create_device_sensor(tado, home["name"], home["id"], variable,)
            for variable in DEVICE_SENSORS
        ]
    )

    add_entities(sensor_items, True)


def create_zone_sensor(tado, name, zone_id, variable):
    """Create a zone sensor."""
    return TadoSensor(tado, name, "zone", zone_id, variable)


def create_device_sensor(tado, name, device_id, variable):
    """Create a device sensor."""
    return TadoSensor(tado, name, "device", device_id, variable)


class TadoSensor(Entity):
    """Representation of a tado Sensor."""

    def __init__(self, tado, zone_name, zone_type, zone_id, zone_variable):
        """Initialize of the Tado Sensor."""
        self._tado = tado

        self.zone_name = zone_name
        self.zone_id = zone_id
        self.zone_variable = zone_variable
        self.zone_type = zone_type

        self._unique_id = f"{zone_variable} {zone_id}"

        self._state = None
        self._state_attributes = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""
        async_dispatcher_connect(
            self.hass,
            SIGNAL_TADO_UPDATE_RECEIVED.format(self.zone_id),
            self._handle_update,
        )
        self._tado.add_sensor(self.zone_id, self.zone_type)
        await self.hass.async_add_executor_job(self._tado.update)

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.zone_name} {self.zone_variable}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.zone_variable == "temperature":
            return self.hass.config.units.temperature_unit
        if self.zone_variable == "humidity":
            return "%"
        if self.zone_variable == "heating":
            return "%"
        if self.zone_variable == "ac":
            return ""

    @property
    def icon(self):
        """Icon for the sensor."""
        if self.zone_variable == "temperature":
            return "mdi:thermometer"
        if self.zone_variable == "humidity":
            return "mdi:water-percent"

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    def _handle_update(self, data):
        """Handle update callbacks."""
        unit = TEMP_CELSIUS

        if self.zone_variable == "temperature":
            if "sensorDataPoints" in data:
                sensor_data = data["sensorDataPoints"]
                temperature = float(sensor_data["insideTemperature"]["celsius"])

                self._state = self.hass.config.units.temperature(temperature, unit)
                self._state_attributes = {
                    "time": sensor_data["insideTemperature"]["timestamp"],
                    "setting": 0,  # setting is used in climate device
                }

                # temperature setting will not exist when device is off
                if (
                    "temperature" in data["setting"]
                    and data["setting"]["temperature"] is not None
                ):
                    temperature = float(data["setting"]["temperature"]["celsius"])

                    self._state_attributes[
                        "setting"
                    ] = self.hass.config.units.temperature(temperature, unit)

        elif self.zone_variable == "humidity":
            if "sensorDataPoints" in data:
                sensor_data = data["sensorDataPoints"]
                self._state = float(sensor_data["humidity"]["percentage"])
                self._state_attributes = {"time": sensor_data["humidity"]["timestamp"]}

        elif self.zone_variable == "power":
            if "setting" in data:
                self._state = data["setting"]["power"]

        elif self.zone_variable == "link":
            if "link" in data:
                self._state = data["link"]["state"]

        elif self.zone_variable == "heating":
            if "activityDataPoints" in data:
                activity_data = data["activityDataPoints"]

                if (
                    "heatingPower" in activity_data
                    and activity_data["heatingPower"] is not None
                ):
                    self._state = float(activity_data["heatingPower"]["percentage"])
                    self._state_attributes = {
                        "time": activity_data["heatingPower"]["timestamp"]
                    }

        elif self.zone_variable == "ac":
            if "activityDataPoints" in data:
                activity_data = data["activityDataPoints"]

                if "acPower" in activity_data and activity_data["acPower"] is not None:
                    self._state = activity_data["acPower"]["value"]
                    self._state_attributes = {
                        "time": activity_data["acPower"]["timestamp"]
                    }

        elif self.zone_variable == "tado bridge status":
            if "connectionState" in data:
                self._state = data["connectionState"]["value"]

        elif self.zone_variable == "tado mode":
            if "tadoMode" in data:
                self._state = data["tadoMode"]

        elif self.zone_variable == "overlay":
            if "overlay" in data and data["overlay"] is not None:
                self._state = True
                self._state_attributes = {
                    "termination": data["overlay"]["termination"]["type"]
                }
            else:
                self._state = False
                self._state_attributes = {}

        elif self.zone_variable == "early start":
            if "preparation" in data and data["preparation"] is not None:
                self._state = True
            else:
                self._state = False

        self.schedule_update_ha_state()
