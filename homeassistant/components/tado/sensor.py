"""Support for Tado sensors for each zone."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DATA,
    DOMAIN,
    SIGNAL_TADO_UPDATE_RECEIVED,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
    TYPE_HOT_WATER,
)
from .entity import TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Tado sensor platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]
    zones = tado.zones
    entities = []

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


class TadoZoneSensor(TadoZoneEntity, Entity):
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
            return PERCENTAGE
        if self.zone_variable == "heating":
            return PERCENTAGE
        if self.zone_variable == "ac":
            return None

    @property
    def icon(self):
        """Icon for the sensor."""
        if self.zone_variable == "temperature":
            return "mdi:thermometer"
        if self.zone_variable == "humidity":
            return "mdi:water-percent"

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
            self._state = self.hass.config.units.temperature(
                self._tado_zone_data.current_temp, TEMP_CELSIUS
            )
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
