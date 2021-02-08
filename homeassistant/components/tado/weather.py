"""Support for the Tado weather service."""
from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTRIBUTION,
    CONDITIONS_MAP,
    DATA,
    DOMAIN,
    SIGNAL_TADO_UPDATE_RECEIVED,
)
from .entity import TadoHomeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Tado weather platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]

    async_add_entities([TadoWeatherEntity(tado)], True)


def format_condition(condition: str) -> str:
    """Return condition from dict CONDITIONS_MAP."""
    for key, value in CONDITIONS_MAP.items():
        if condition in value:
            return key
    return condition


class TadoWeatherEntity(TadoHomeEntity, WeatherEntity):
    """Define a Tado weather entity."""

    def __init__(self, tado):
        """Initialize."""
        super().__init__(tado)
        self._tado = tado
        self._data = self._tado.data["weather"]

        self._name = tado.home_name
        self._unique_id = f"weather {tado.home_id}"

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
        self._async_update_weather_data()

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def condition(self):
        """Return the current condition."""
        condition = self._data["weatherState"]["value"]
        return format_condition(condition)

    @property
    def humidity(self):
        """Not supported."""
        return None

    @property
    def temperature(self):
        """Return the temperature."""
        return self._data["outsideTemperature"]["celsius"]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @callback
    def _async_update_callback(self):
        """Update and write state."""
        self._async_update_weather_data()
        self.async_write_ha_state()

    @callback
    def _async_update_weather_data(self):
        """Handle update callbacks."""
        self._data = self._tado.data["weather"]
