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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CO2signal sensor."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )
    )

    return True


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the CO2signal sensor."""
    async_add_entities(
        [
            CO2Sensor(
                entry.data[CONF_API_KEY],
                entry.data.get(CONF_COUNTRY_CODE),
                entry.data.get(CONF_LATITUDE),
                entry.data.get(CONF_LONGITUDE),
                entry_id=entry.entry_id,
            )
        ],
        True,
    )


class CO2Sensor(SensorEntity):
    """Implementation of the CO2Signal sensor."""

    _attr_icon = "mdi:molecule-co2"
    _attr_unit_of_measurement = CO2_INTENSITY_UNIT

    def __init__(self, token, country_code, lat, lon, entry_id=None):
        """Initialize the sensor."""
        self._token = token
        self._country_code = country_code
        self._latitude = lat
        self._longitude = lon

        if country_code is not None:
            device_name = country_code
        else:
            device_name = f"{round(self._latitude, 2)}/{round(self._longitude, 2)}"

        self._attr_name = f"CO2 intensity - {device_name}"
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

        if self._country_code is not None:
            data = CO2Signal.get_latest_carbon_intensity(
                self._token, country_code=self._country_code
            )
        else:
            data = CO2Signal.get_latest_carbon_intensity(
                self._token, latitude=self._latitude, longitude=self._longitude
            )

        self._attr_state = round(data, 2)
