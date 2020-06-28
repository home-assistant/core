"""Support for iammeter via local API."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from iammeter import real_time_api
from iammeter.power_meter import IamMeterError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import debounce
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_DEVICE_NAME = "IamMeter"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_DEVICE_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SCAN_INTERVAL = timedelta(seconds=30)
PLATFORM_TIMEOUT = 8


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup."""
    config_host = config[CONF_HOST]
    config_port = config[CONF_PORT]
    config_name = config[CONF_NAME]
    try:
        with async_timeout.timeout(PLATFORM_TIMEOUT):
            api = await real_time_api(config_host, config_port)
    except (IamMeterError, asyncio.TimeoutError):
        _LOGGER.error("Device is not ready")
        raise PlatformNotReady

    async def async_update_data():
        try:
            with async_timeout.timeout(PLATFORM_TIMEOUT):
                return await api.get_data()
        except (IamMeterError, asyncio.TimeoutError):
            raise UpdateFailed

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DEFAULT_DEVICE_NAME,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=0.3, immediate=True
        ),
    )
    await coordinator.async_refresh()
    entities = []
    for sensor_name, (row, idx, unit) in api.iammeter.sensor_map().items():
        serial_number = api.iammeter.serial_number
        uid = f"{serial_number}-{row}-{idx}"
        entities.append(IamMeter(coordinator, uid, sensor_name, unit, config_name))
    async_add_entities(entities)


class IamMeter(Entity):
    """Class for a sensor."""

    def __init__(self, coordinator, uid, sensor_name, unit, dev_name):
        """Initialize an iammeter sensor."""
        self.coordinator = coordinator
        self.uid = uid
        self.sensor_name = sensor_name
        self.unit = unit
        self.dev_name = dev_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.data[self.sensor_name]

    @property
    def unique_id(self):
        """Return unique id."""
        return self.uid

    @property
    def name(self):
        """Name of this iammeter attribute."""
        return f"{self.dev_name} {self.sensor_name}"

    @property
    def icon(self):
        """Icon for each sensor."""
        return "mdi:flash"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.unit

    @property
    def should_poll(self):
        """Poll needed."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()
