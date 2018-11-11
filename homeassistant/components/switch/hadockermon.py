"""
Support for controlling HA Dockermon.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.hadockermon/
"""

import logging

import voluptuous as vol

from homeassistant.components.switch import (DOMAIN, PLATFORM_SCHEMA,
        SwitchDevice)
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_NAME,
        CONF_USERNAME, CONF_PASSWORD, CONF_SSL, CONF_VERIFY_SSL)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pydockermon==1.0.0']
DEFAULT_NAME = 'HA Dockermon {0}'

CONF_CONTAINERS = 'containers'

ATTR_CONTAINER = 'container'
ATTR_STATUS = 'status'
ATTR_IMAGE = 'image'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default=8126): cv.port,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
    vol.Optional(CONF_CONTAINERS, default=None):
        vol.All(cv.ensure_list, [cv.string]),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the device."""
    from pydockermon.api import API

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    username = config.get(CONF_PASSWORD)
    password = config.get(CONF_PASSWORD)
    ssl = config[CONF_SSL]
    verify_ssl = config[CONF_VERIFY_SSL]
    device_name = config.get(CONF_NAME)
    containers = config[CONF_CONTAINERS]
    session = async_get_clientsession(hass, verify_ssl)
    api = API(hass.loop, session, host, port, username, password, ssl)
    devices = []
    await api.list_containers()
    for container in api.all_containers['data']:
        if not containers or container in containers:
            if not container.startswith("addon_"):
                devices.append(HADockermonSwitch(api, device_name, container))

    async def restart_container(call):
        """Restart a container."""
        container = call.data.get(ATTR_CONTAINER)
        _LOGGER.info("Restarting %s", container)
        await api.container_restart(container)

    hass.services.async_register(DOMAIN, 'hadockermon_restart', restart_container)

    async_add_entities(devices, True)


class HADockermonSwitch(SwitchDevice):
    """Representation of a HA Dockermon switch."""

    def __init__(self, api, device_name, container):
        """Initialize a HA Dockermon switch."""
        self.api = api
        self.device_name = device_name
        self.container = container
        if not self.device_name:
            self.device_name = DEFAULT_NAME.format(self.container)
        self._state = None
        self._status = None
        self._image = None

    async def async_turn_on(self):
        """Turn on the switch."""
        await self.api.container_start(self.container)

    async def async_turn_off(self):
        """Turn off the switch."""
        await self.api.container_stop(self.container)

    async def async_update(self):
        """Update the current switch status."""
        state = await self.api.container_state(self.container)
        try:
            self._state = state['data']['state']
        except (TypeError, KeyError):
            _LOGGER.debug("Could not fetch state for %s", self.container)
        try:
            self._status = state['data']['status']
        except (TypeError, KeyError):
            _LOGGER.debug("Could not fetch status for %s", self.container)
        try:
            self._image = state['data']['image']
        except (TypeError, KeyError):
            _LOGGER.debug("Could not fetch image for %s", self.container)

    @property
    def name(self):
        """Return the switch name."""
        return self.device_name

    @property
    def is_on(self):
        """Return true if switch is on."""
        state = True if self._state == 'running' else False
        return state

    @property
    def icon(self):
        """Set the device icon."""
        return 'mdi:docker'

    @property
    def device_state_attributes(self):
        """Set device attributes."""
        return {
            ATTR_STATUS: self._status,
            ATTR_IMAGE: self._image,
        }
