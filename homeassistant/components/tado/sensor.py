"""Support for Tado sensors for each zone."""
import logging

from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DATA, DOMAIN, SIGNAL_TADO_UPDATE_RECEIVED
from .const import TYPE_AIR_CONDITIONING, TYPE_HEATING, TYPE_HOT_WATER

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
        "open window",
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
    api_list = hass.data[DOMAIN][DATA]

    entities = []

    for tado in api_list:
        # Create zone sensors

        for zone in tado.zones:
            entities.extend(
                [
                    create_zone_sensor(tado, zone["name"], zone["id"], variable)
                    for variable in ZONE_SENSORS.get(zone["type"])
                ]
            )

        # Create device sensors
        for home in tado.devices:
            entities.extend(
                [
                    create_device_sensor(tado, home["name"], home["id"], variable)
                    for variable in DEVICE_SENSORS
                ]
            )

    add_entities(entities, True)


def create_zone_sensor(tado, name, zone_id, variable):
    """Create a zone sensor."""
    return TadoSensor(tado, name, "zone", zone_id, variable)


def create_device_sensor(tado, name, device_id, variable):
    """Create a device sensor."""
    return TadoSensor(tado, name, "device", device_id, variable)


class TadoSensor(Entity):
    """Representation of a tado Sensor."""

    def __init__(self, tado, zone_name, sensor_type, zone_id, zone_variable):
        """Initialize of the Tado Sensor."""
        self._tado = tado

        self.zone_name = zone_name
        self.zone_id = zone_id
        self.zone_variable = zone_variable
        self.sensor_type = sensor_type

        self._unique_id = f"{zone_variable} {zone_id} {tado.device_id}"

        self._state = None
        self._state_attributes = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        @callback
        def async_update_callback():
            """Schedule an entity update."""
            self.async_schedule_update_ha_state(True)

        async_dispatcher_connect(
            self.hass,
            SIGNAL_TADO_UPDATE_RECEIVED.format(self.sensor_type, self.zone_id),
            async_update_callback,
        )

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
            return UNIT_PERCENTAGE
        if self.zone_variable == "heating":
            return UNIT_PERCENTAGE
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

    def update(self):
        """Handle update callbacks."""
        try:
            data = self._tado.data[self.sensor_type][self.zone_id]
        except KeyError:
            return

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
            self._state = "overlay" in data and data["overlay"] is not None
            self._state_attributes = (
                {"termination": data["overlay"]["termination"]["type"]}
                if self._state
                else {}
            )

        elif self.zone_variable == "early start":
            self._state = "preparation" in data and data["preparation"] is not None

        elif self.zone_variable == "open window":
            self._state = "openWindow" in data and data["openWindow"] is not None
            self._state_attributes = data["openWindow"] if self._state else {}
