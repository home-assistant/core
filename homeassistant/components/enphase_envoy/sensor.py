"""Support for Enphase Envoy solar energy monitor."""

from datetime import timedelta
import logging

import async_timeout
from envoy_reader.envoy_reader import EnvoyReader
import httpcore
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    "production": ("Envoy Current Energy Production", POWER_WATT),
    "daily_production": ("Envoy Today's Energy Production", ENERGY_WATT_HOUR),
    "seven_days_production": (
        "Envoy Last Seven Days Energy Production",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_production": ("Envoy Lifetime Energy Production", ENERGY_WATT_HOUR),
    "consumption": ("Envoy Current Energy Consumption", POWER_WATT),
    "daily_consumption": ("Envoy Today's Energy Consumption", ENERGY_WATT_HOUR),
    "seven_days_consumption": (
        "Envoy Last Seven Days Energy Consumption",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_consumption": ("Envoy Lifetime Energy Consumption", ENERGY_WATT_HOUR),
    "inverters": ("Envoy Inverter", POWER_WATT),
}

ICON = "mdi:flash"
CONST_DEFAULT_HOST = "envoy"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_IP_ADDRESS, default=CONST_DEFAULT_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default="envoy"): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)): vol.All(
            cv.ensure_list, [vol.In(list(SENSORS))]
        ),
        vol.Optional(CONF_NAME, default=""): cv.string,
    }
)


async def async_setup_platform(
    homeassistant, config, async_add_entities, discovery_info=None
):
    """Set up the Enphase Envoy sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    name = config[CONF_NAME]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    envoy_reader = EnvoyReader(ip_address, username, password)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                data = await envoy_reader.update()
                _LOGGER.debug("Retrieved data from API: %s", data)
                if "can't handle event type ConnectionClosed" in str(
                    data.get("inverters_production")
                ):
                    _LOGGER.warning(
                        "Communication error with Enphase Envoy.  Will retrieve data on the next poll."
                    )
                return data
        except httpcore.ProtocolError as err:
            _LOGGER.error("Error communicating with API: %s", err)
        except httpcore.ConnectTimeout as err:
            _LOGGER.error("Timeout error with API: %s", err)

    coordinator = DataUpdateCoordinator(
        homeassistant,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    entities = []
    # Iterate through the list of sensors
    for condition in monitored_conditions:
        if condition == "inverters":
            inverters = coordinator.data.get("inverters_production")
            _LOGGER.debug("Inverter data: %s", inverters)
            if isinstance(inverters, dict):
                for inverter in inverters:
                    entities.append(
                        Envoy(
                            envoy_reader,
                            condition,
                            f"{name}{SENSORS[condition][0]} {inverter}",
                            SENSORS[condition][1],
                            coordinator,
                        )
                    )
                    _LOGGER.debug(
                        "Adding inverter SN: %s - Type: %s.",
                        f"{name}{SENSORS[condition][0]} {inverter}",
                        condition,
                    )
            elif "Unable to connect to Envoy" in inverters:
                _LOGGER.error(
                    "Unable to connect to Enphase Envoy during setup. Inverter entities not added. Please check IP address and credentials are correct."
                )
            elif "can't handle event type ConnectionClosed" in inverters:
                _LOGGER.error(
                    "Communication error with Enphase Envoy during setup. Inverter entities not added."
                )
        else:
            entities.append(
                Envoy(
                    envoy_reader,
                    condition,
                    f"{name}{SENSORS[condition][0]}",
                    SENSORS[condition][1],
                    coordinator,
                )
            )
            _LOGGER.debug(
                "Adding sensor: %s - Type: %s.",
                f"{name}{SENSORS[condition][0]})",
                condition,
            )
    async_add_entities(entities)


class Envoy(Entity):
    """Envoy entity."""

    def __init__(self, envoy_reader, sensor_type, name, unit, coordinator):
        """Initialize Envoy entity."""
        self._envoy_reader = envoy_reader
        self._type = sensor_type
        self._name = name
        self._unit_of_measurement = unit
        self._state = None
        self._last_reported = None

        self.coordinator = coordinator

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._type == "inverters":
            return {"last_reported": self._last_reported}

        return None

    @property
    def should_poll(self):
        """Poll to retrieve latest data from Envoy endpoint."""
        return True

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the energy production data."""
        if self._type != "inverters":
            if isinstance(self.coordinator.data.get(self._type), int):
                self._state = self.coordinator.data.get(self._type)
                _LOGGER.debug("Updating: %s - %s", self._type, self._state)
            else:
                _LOGGER.debug(
                    "Sensor %s isInstance(int) was %s.  Returning None for state.",
                    self._type,
                    isinstance(self.coordinator.data.get(self._type), int),
                )

        elif self._type == "inverters":
            serial_number = self._name.split(" ")[2]
            if isinstance(self.coordinator.data.get("inverters_production"), dict):
                self._state = self.coordinator.data.get("inverters_production").get(
                    serial_number
                )[0]
                self._last_reported = self.coordinator.data.get(
                    "inverters_production"
                ).get(serial_number)[1]
                _LOGGER.debug(
                    "Updating: %s (%s) - %s.", self._type, serial_number, self._state,
                )
            else:
                _LOGGER.debug(
                    "Data inverter (%s) isInstance(dict) was %s.  Using previous state: %s",
                    serial_number,
                    isinstance(self.coordinator.data.get("inverters_production"), dict),
                    self._state,
                )
