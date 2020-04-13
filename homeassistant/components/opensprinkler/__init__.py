"""Opensprinkler integration."""
import asyncio
import logging

from pyopensprinkler import OpenSprinkler
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
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
SUPPORTED_DOMAINS = ["binary_sensor", "scene", "sensor", "switch"]

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

    tasks = [
        async_setup_device(hass, deviceConfig) for deviceConfig in conf[CONF_DEVICES]
    ]
    if tasks:
        await asyncio.wait(tasks)

    return True


async def async_setup_device(hass: HomeAssistant, config: dict):
    """Set up opensprinkler device."""
    password = config.get(CONF_PASSWORD)
    host = f"{config.get(CONF_HOST)}:{config.get(CONF_PORT, DEFAULT_PORT)}"
    opensprinkler = OpenSprinkler(host, password)

    name = config.get(CONF_NAME)
    hass.data[DOMAIN][DATA_DEVICES][name] = opensprinkler
    default_seconds = config.get(CONF_RUN_SECONDS)

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                component,
                DOMAIN,
                {"name": name, "default_seconds": default_seconds},
                config,
            )
        )

    return True


class OpensprinklerEntity(RestoreEntity):
    """Define a generic opensprinkler entity."""

    def __init__(self):
        """Initialize."""
        self._state = None

    def _get_state(self):
        """Retrieve the state."""
        raise NotImplementedError

    @Throttle(SCAN_INTERVAL)
    async def async_update(self) -> None:
        """Update latest state."""
        self._state = self._get_state()
        self.async_write_ha_state()


class OpensprinklerBinarySensor(OpensprinklerEntity):
    """Define a generic opensprinkler binary sensor."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if self._state is not None or old_state is None:
            return

        if old_state.state == STATE_ON:
            self._state = True
        else:
            self._state = False


class OpensprinklerSensor(OpensprinklerEntity):
    """Define a generic opensprinkler sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if self._state is not None or old_state is None:
            return

        self._state = old_state.state
