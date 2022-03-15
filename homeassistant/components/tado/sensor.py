"""Support for Tado sensors for each zone."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONDITIONS_MAP,
    DATA,
    DOMAIN,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
    TYPE_HOT_WATER,
)
from .entity import TadoHomeEntity, TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

HOME_SENSORS = {
    "outdoor temperature",
    "solar percentage",
    "weather condition",
}

ZONE_SENSORS = {
    TYPE_HEATING: [
        "temperature",
        "humidity",
        "heating",
        "tado mode",
    ],
    TYPE_AIR_CONDITIONING: [
        "temperature",
        "humidity",
        "ac",
        "tado mode",
    ],
    TYPE_HOT_WATER: ["tado mode"],
}


def format_condition(condition: str) -> str:
    """Return condition from dict CONDITIONS_MAP."""
    for key, value in CONDITIONS_MAP.items():
        if condition in value:
            return key
    return condition


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tado sensor platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]
    zones = tado.zones
    entities: list[SensorEntity] = []

    # Create home sensors
    entities.extend([TadoHomeSensor(tado, variable) for variable in HOME_SENSORS])

    # Create zone sensors
    for zone in zones:
        zone_type = zone["type"]
        if zone_type not in ZONE_SENSORS:
            _LOGGER.warning("Unknown zone type skipped: %s", zone_type)
            continue

        entities.extend(
            [
                TadoZoneSensor(tado, zone["name"], zone["id"], variable)
                for variable in ZONE_SENSORS[zone_type]
            ]
        )

    if entities:
        async_add_entities(entities, True)


class TadoHomeSensor(TadoHomeEntity, SensorEntity):
    """Representation of a Tado Sensor."""

    def __init__(self, tado, home_variable):
        """Initialize of the Tado Sensor."""
        super().__init__(tado)
        self._tado = tado

        self.home_variable = home_variable

        self._unique_id = f"{home_variable} {tado.home_id}"

        self._state = None
        self._state_attributes = None
        self._tado_weather_data = self._tado.data["weather"]

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "weather", "data"
                ),
                self._async_update_callback,
            )
        )
        self._async_update_home_data()

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._tado.home_name} {self.home_variable}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._state_attributes

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.home_variable in ["temperature", "outdoor temperature"]:
            return TEMP_CELSIUS
        if self.home_variable == "solar percentage":
            return PERCENTAGE
        if self.home_variable == "weather condition":
            return None

    @property
    def device_class(self):
        """Return the device class."""
        if self.home_variable == "outdoor temperature":
            return SensorDeviceClass.TEMPERATURE
        return None

    @property
    def state_class(self):
        """Return the state class."""
        if self.home_variable in ["outdoor temperature", "solar percentage"]:
            return SensorStateClass.MEASUREMENT
        return None

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_home_data()
        self.async_write_ha_state()

    @callback
    def _async_update_home_data(self):
        """Handle update callbacks."""
        try:
            self._tado_weather_data = self._tado.data["weather"]
        except KeyError:
            return

        if self.home_variable == "outdoor temperature":
            self._state = self._tado_weather_data["outsideTemperature"]["celsius"]
            self._state_attributes = {
                "time": self._tado_weather_data["outsideTemperature"]["timestamp"],
            }

        elif self.home_variable == "solar percentage":
            self._state = self._tado_weather_data["solarIntensity"]["percentage"]
            self._state_attributes = {
                "time": self._tado_weather_data["solarIntensity"]["timestamp"],
            }

        elif self.home_variable == "weather condition":
            self._state = format_condition(
                self._tado_weather_data["weatherState"]["value"]
            )
            self._state_attributes = {
                "time": self._tado_weather_data["weatherState"]["timestamp"]
            }


class TadoZoneSensor(TadoZoneEntity, SensorEntity):
    """Representation of a tado Sensor."""

    def __init__(self, tado, zone_name, zone_id, zone_variable):
        """Initialize of the Tado Sensor."""
        self._tado = tado
        super().__init__(zone_name, tado.home_id, zone_id)

        self.zone_variable = zone_variable

        self._unique_id = f"{zone_variable} {zone_id} {tado.home_id}"

        self._state = None
        self._state_attributes = None
        self._tado_zone_data = None

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "zone", self.zone_id
                ),
                self._async_update_callback,
            )
        )
        self._async_update_zone_data()

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.zone_name} {self.zone_variable}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._state_attributes

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.zone_variable == "temperature":
            return TEMP_CELSIUS
        if self.zone_variable == "humidity":
            return PERCENTAGE
        if self.zone_variable == "heating":
            return PERCENTAGE
        if self.zone_variable == "ac":
            return None

    @property
    def device_class(self):
        """Return the device class."""
        if self.zone_variable == "humidity":
            return SensorDeviceClass.HUMIDITY
        if self.zone_variable == "temperature":
            return SensorDeviceClass.TEMPERATURE
        return None

    @property
    def state_class(self):
        """Return the state class."""
        if self.zone_variable in ["ac", "heating", "humidity", "temperature"]:
            return SensorStateClass.MEASUREMENT
        return None

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_zone_data()
        self.async_write_ha_state()

    @callback
    def _async_update_zone_data(self):
        """Handle update callbacks."""
        try:
            self._tado_zone_data = self._tado.data["zone"][self.zone_id]
        except KeyError:
            return

        if self.zone_variable == "temperature":
            self._state = self._tado_zone_data.current_temp
            self._state_attributes = {
                "time": self._tado_zone_data.current_temp_timestamp,
                "setting": 0,  # setting is used in climate device
            }

        elif self.zone_variable == "humidity":
            self._state = self._tado_zone_data.current_humidity
            self._state_attributes = {
                "time": self._tado_zone_data.current_humidity_timestamp
            }

        elif self.zone_variable == "heating":
            self._state = self._tado_zone_data.heating_power_percentage
            self._state_attributes = {
                "time": self._tado_zone_data.heating_power_timestamp
            }

        elif self.zone_variable == "ac":
            self._state = self._tado_zone_data.ac_power
            self._state_attributes = {"time": self._tado_zone_data.ac_power_timestamp}

        elif self.zone_variable == "tado mode":
            self._state = self._tado_zone_data.tado_mode
