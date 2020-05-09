"""Opensprinkler integration."""
import asyncio
from datetime import timedelta
import logging

from pyopensprinkler import OpenSprinkler
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle

from .const import (
    CONF_RUN_SECONDS,
    DATA_DEVICES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RUN_SECONDS,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONF_DEVICES = "devices"
PLATFORMS = ["binary_sensor", "scene", "sensor", "switch"]

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_RUN_SECONDS, default=DEFAULT_RUN_SECONDS): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the opensprinkler component from YAML."""

    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_DEVICES, {})

    if not conf:
        return True

    for deviceConfig in conf[CONF_DEVICES]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=deviceConfig
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Opensprinkler from a config entry."""
    password = entry.data.get(CONF_PASSWORD)
    host = f"{entry.data.get(CONF_HOST)}:{entry.data.get(CONF_PORT, DEFAULT_PORT)}"
    hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job(
        OpenSprinkler, host, password
    )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OpensprinklerCoordinator:
    """Define a generic opensprinkler entity."""

    def __init__(self, hass, device):
        """Initialize."""
        self._cancel_time_interval_listener = None
        self._hass = hass
        self._device = device

    async def _async_update_listener_action(self, now):
        """Define an async_track_time_interval action to update data."""
        await self._hass.async_add_executor_job(self._device.update_state)

    async def async_register_time_interval_listener(self):
        """Register time interval listener."""
        if not self._cancel_time_interval_listener:
            self._cancel_time_interval_listener = async_track_time_interval(
                self._hass, self._async_update_listener_action, timedelta(seconds=15),
            )

    @callback
    def deregister_time_interval_listener(self):
        """Deregister time interval listener."""
        if self._cancel_time_interval_listener:
            self._cancel_time_interval_listener()
            self._cancel_time_interval_listener = None


class OpensprinklerEntity(RestoreEntity):
    """Define a generic opensprinkler entity."""

    def __init__(self, coordinator=None):
        """Initialize."""
        self._state = None
        self._coordinator = coordinator

    def _get_state(self):
        """Retrieve the state."""
        raise NotImplementedError

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(async_dispatcher_connect(self.hass, DOMAIN, self.update))
        await self._coordinator.async_register_time_interval_listener()
        self.update()

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listeners and deregister API interest."""
        super().async_will_remove_from_hass()
        self._coordinator.deregister_time_interval_listener()

    @Throttle(SCAN_INTERVAL)
    def update(self) -> None:
        """Update latest state."""
        self._state = self._get_state()


class OpensprinklerBinarySensor(OpensprinklerEntity):
    """Define a generic opensprinkler binary sensor."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state


class OpensprinklerSensor(OpensprinklerEntity):
    """Define a generic opensprinkler sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
