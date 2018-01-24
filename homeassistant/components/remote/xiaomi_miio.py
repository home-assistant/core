"""
Support for the Xiaomi IR Remote (Chuangmi IR).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ir_remote.xiaomi_miio/
"""
import asyncio
import logging

from datetime import timedelta

import voluptuous as vol

import homeassistant.components.remote as remote
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_TOKEN, CONF_TIMEOUT,
    ATTR_ENTITY_ID, ATTR_HIDDEN, CONF_COMMAND)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

REQUIREMENTS = ['python-miio==0.3.4']

_LOGGER = logging.getLogger(__name__)

SERVICE_LEARN = 'xiaomi_miio_learn_command'
SERVICE_SEND = 'xiaomi_miio_send_command'
PLATFORM = 'python_miio'

CONF_SLOT = 'slot'
CONF_COMMANDS = 'commands'

DEFAULT_TIMEOUT = 10
DEFAULT_SLOT = 1

LEARN_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.string,
    vol.Optional(CONF_TIMEOUT, default=10):
        vol.All(int, vol.Range(min=0)),
    vol.Optional(CONF_SLOT, default=1):
        vol.All(int, vol.Range(min=1, max=1000000)),
})

COMMAND_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMAND): cv.ensure_list
    })

PLATFORM_SCHEMA = remote.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_TIMEOUT, default=10):
        vol.All(int, vol.Range(min=0)),
    vol.Optional(CONF_SLOT, default=1):
        vol.All(int, vol.Range(min=1, max=1000000)),
    vol.Optional(ATTR_HIDDEN, default=True): cv.boolean,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_COMMANDS, default={}):
        vol.Schema({cv.slug: COMMAND_SCHEMA}),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Xiaomi IR Remote (Chuangmi IR) platform."""
    from miio import ChuangmiIr
    from construct import ChecksumError

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
    device = ChuangmiIr(host, token)

    try:
        device.info()

    # This should be DeviceError but python-miio returns wrong except.
    except ChecksumError as ex:
        _LOGGER.error("Token not accepted by device : %s", ex)
        return

    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    entity_id = config.get(CONF_NAME, "xiaomi_miio_" +
                           host.replace('.', '_'))
    slot = config.get(CONF_SLOT)
    timeout = config.get(CONF_TIMEOUT)

    hidden = config.get(ATTR_HIDDEN)

    xiaomi_miio_remote = XiaomiMiioRemote(
        entity_id, device, slot, timeout, hidden, config.get(CONF_COMMANDS))

    hass.data[PLATFORM][
        entity_id.replace(' ', '_').lower()] = xiaomi_miio_remote

    async_add_devices([xiaomi_miio_remote])

    @asyncio.coroutine
    def _learn_command(call):
        """Handle a learn command."""
        entity_id = call.data.get('entity_id').split('.')[1]

        entity = hass.data[PLATFORM][entity_id]

        device = entity.device

        slot = call.data.get(CONF_SLOT, entity.slot)

        yield from hass.async_add_job(device.learn, slot)

        timeout = call.data.get(CONF_TIMEOUT, entity.timeout)

        _LOGGER.info("Press the key you want Home Assistant to learn")
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=timeout):
            command = yield from hass.async_add_job(
                device.read, slot)
            if command['code']:
                log_msg = "Received command is: {}".\
                          format(command['code'])
                _LOGGER.info(log_msg)
                hass.components.persistent_notification.async_create(
                    log_msg, title='Xiaomi Miio Remote')
                return
            yield from asyncio.sleep(1, loop=hass.loop)
        _LOGGER.error("Timeout. No infrared command captured")
        hass.components.persistent_notification.async_create(
            "Timeout. No infrared command captured",
            title='Xiaomi Miio Remote')

    hass.services.async_register(remote.DOMAIN, SERVICE_LEARN, _learn_command,
                                 schema=LEARN_COMMAND_SCHEMA)


class XiaomiMiioRemote(Entity):
    """Representation of a Xiaomi Miio Remote device."""

    def __init__(self, friendly_name, device,
                 slot, timeout, hidden, commands):
        """Initialize the remote."""
        self._name = friendly_name
        self._device = device
        self._is_hidden = hidden
        self._slot = slot
        self._timeout = timeout
        self._state = False
        self._commands = commands

    @property
    def name(self):
        """Return the name of the remote."""
        return self._name

    @property
    def device(self):
        """Return the remote object."""
        return self._device

    @property
    def hidden(self):
        """Return if we should hide entity."""
        return self._is_hidden

    @property
    def slot(self):
        """Return the slot to save learned command."""
        return self._slot

    @property
    def timeout(self):
        """Return the timeout for learning command."""
        return self._timeout

    @property
    def is_on(self):
        """Return False if device is unreachable, else True."""
        from miio import DeviceException
        try:
            self.device.info()
            return True
        except DeviceException:
            return False

    @property
    def device_state_attributes(self):
        """Hide remote by default."""
        if self._is_hidden:
            return {'hidden': 'true'}
        else:
            return

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""

    @asyncio.coroutine
    def _send_command(self, payload):
        """Send a packet."""
        from miio import DeviceException

        _LOGGER.debug("Sending payload: '%s'", payload)
        try:
            yield from self.hass.async_add_job(
                self.device.play, payload, None)
            return True
        except DeviceException as e:
            _LOGGER.error(
                "Transmit of IR command failed, %s, exception: %s",
                payload, e)
            return False

    @asyncio.coroutine
    def async_send_command(self, command, **kwargs):
        """Wrapper for _send_command."""
        for payload in command:
            if payload in self._commands:
                for local_payload in self._commands[payload][CONF_COMMAND]:
                    yield from self._send_command(local_payload)
            else:
                yield from self._send_command(payload)
