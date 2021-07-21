"""Support for the CO2signal platform."""
from datetime import timedelta
import logging

import CO2Signal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_NAME,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_TOKEN,
    ENERGY_KILO_WATT_HOUR,
)
import homeassistant.helpers.config_validation as cv

from .const import ATTRIBUTION, CONF_COUNTRY_CODE, DOMAIN, MSG_LOCATION
from .util import get_extra_name

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=3)

CO2_INTENSITY_UNIT = f"CO2eq/{ENERGY_KILO_WATT_HOUR}"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coords", msg=MSG_LOCATION): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coords", msg=MSG_LOCATION): cv.longitude,
        vol.Optional(CONF_COUNTRY_CODE): cv.string,
    }
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CO2signal sensor."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the CO2signal sensor."""
    name = "CO2 intensity"
    if extra_name := get_extra_name(hass, entry.data):
        name += f" - {extra_name}"

    async_add_entities(
        [
            CO2Sensor(
                name,
                entry.data,
                entry_id=entry.entry_id,
            )
        ],
        True,
    )


class CO2Sensor(SensorEntity):
    """Implementation of the CO2Signal sensor."""

    _attr_icon = "mdi:molecule-co2"
    _attr_unit_of_measurement = CO2_INTENSITY_UNIT

    def __init__(self, name, config, entry_id):
        """Initialize the sensor."""
        self._config = config
        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, entry_id)},
            ATTR_NAME: "CO2 signal",
            ATTR_MANUFACTURER: "Tmrow.com",
            "entry_type": "service",
        }
        self._attr_unique_id = f"{entry_id}_co2intensity"

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Update data for %s", self.name)

        if CONF_COUNTRY_CODE in self._config:
            kwargs = {"country_code": self._config[CONF_COUNTRY_CODE]}
        elif CONF_LATITUDE in self._config:
            kwargs = {
                "latitude": self._config[CONF_LATITUDE],
                "longitude": self._config[CONF_LONGITUDE],
            }
        else:
            kwargs = {
                "latitude": self.hass.config.latitude,
                "longitude": self.hass.config.longitude,
            }

        self._attr_state = round(
            CO2Signal.get_latest_carbon_intensity(self._config[CONF_API_KEY], **kwargs),
            2,
        )
