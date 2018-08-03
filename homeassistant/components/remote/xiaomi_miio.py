"""
Support for the Xiaomi IR Remote (Chuangmi IR).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/remote.xiaomi_miio/
"""
import asyncio
import logging
import time

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.remote import (
    PLATFORM_SCHEMA, DOMAIN, ATTR_NUM_REPEATS, ATTR_DELAY_SECS,
    DEFAULT_DELAY_SECS, RemoteDevice)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_TOKEN, CONF_TIMEOUT,
    ATTR_ENTITY_ID, ATTR_HIDDEN, CONF_COMMAND)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

REQUIREMENTS = ['python-miio==0.4.0', 'construct==2.9.41']

_LOGGER = logging.getLogger(__name__)

SERVICE_LEARN = 'xiaomi_miio_learn_command'
DATA_KEY = 'remote.xiaomi_miio'

CONF_SLOT = 'slot'
CONF_COMMANDS = 'commands'

DEFAULT_TIMEOUT = 10
DEFAULT_SLOT = 1

LEARN_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): vol.All(str),
    vol.Optional(CONF_TIMEOUT, default=10):
        vol.All(int, vol.Range(min=0)),
    vol.Optional(CONF_SLOT, default=1):
        vol.All(int, vol.Range(min=1, max=1000000)),
})

COMMAND_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMAND): vol.All(cv.ensure_list, [cv.string])
    })

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT):
        vol.All(int, vol.Range(min=0)),
    vol.Optional(CONF_SLOT, default=DEFAULT_SLOT):
        vol.All(int, vol.Range(min=1, max=1000000)),
    vol.Optional(ATTR_HIDDEN, default=True): cv.boolean,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_COMMANDS, default={}):
        vol.Schema({cv.slug: COMMAND_SCHEMA}),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Xiaomi IR Remote (Chuangmi IR) platform."""
    from miio import ChuangmiIr, DeviceException

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    # The Chuang Mi IR Remote Controller wants to be re-discovered every
    # 5 minutes. As long as polling is disabled the device should be
    # re-discovered (lazy_discover=False) in front of every command.
    device = ChuangmiIr(host, token, lazy_discover=False)

    # Check that we can communicate with device.
    try:
        device_info = device.info()
        model = device_info.model
        unique_id = "{}-{}".format(model, device_info.mac_address)
        _LOGGER.info("%s %s %s detected",
                     model,
                     device_info.firmware_version,
                     device_info.hardware_version)
    except DeviceException as ex:
        _LOGGER.error("Device unavailable or token incorrect: %s", ex)
        raise PlatformNotReady

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    friendly_name = config.get(CONF_NAME, "xiaomi_miio_" +
                               host.replace('.', '_'))
    slot = config.get(CONF_SLOT)
    timeout = config.get(CONF_TIMEOUT)

    hidden = config.get(ATTR_HIDDEN)

    xiaomi_miio_remote = XiaomiMiioRemote(friendly_name, device, unique_id,
                                          slot, timeout, hidden,
                                          config.get(CONF_COMMANDS))

    hass.data[DATA_KEY][host] = xiaomi_miio_remote

    async_add_devices([xiaomi_miio_remote])

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle a learn command."""
        if service.service != SERVICE_LEARN:
            _LOGGER.error("We should not handle service: %s", service.service)
            return

        entity_id = service.data.get(ATTR_ENTITY_ID)
        entity = None
        for remote in hass.data[DATA_KEY].values():
            if remote.entity_id == entity_id:
                entity = remote

        if not entity:
            _LOGGER.error("entity_id: '%s' not found", entity_id)
            return

        device = entity.device

        slot = service.data.get(CONF_SLOT, entity.slot)

        yield from hass.async_add_job(device.learn, slot)

        timeout = service.data.get(CONF_TIMEOUT, entity.timeout)

        _LOGGER.info("Press the key you want Home Assistant to learn")
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=timeout):
            message = yield from hass.async_add_job(
                device.read, slot)
            _LOGGER.debug("Message received from device: '%s'", message)

            if 'code' in message and message['code']:
                log_msg = "Received command is: {}".format(message['code'])
                _LOGGER.info(log_msg)
                hass.components.persistent_notification.async_create(
                    log_msg, title='Xiaomi Miio Remote')
                return

            if ('error' in message and
                    message['error']['message'] == "learn timeout"):
                yield from hass.async_add_job(device.learn, slot)

            yield from asyncio.sleep(1, loop=hass.loop)

        _LOGGER.error("Timeout. No infrared command captured")
        hass.components.persistent_notification.async_create(
            "Timeout. No infrared command captured",
            title='Xiaomi Miio Remote')

    hass.services.async_register(DOMAIN, SERVICE_LEARN, async_service_handler,
                                 schema=LEARN_COMMAND_SCHEMA)


class XiaomiMiioRemote(RemoteDevice):
    """Representation of a Xiaomi Miio Remote device."""

    def __init__(self, friendly_name, device, unique_id,
                 slot, timeout, hidden, commands):
        """Initialize the remote."""
        self._name = friendly_name
        self._device = device
        self._unique_id = unique_id
        self._is_hidden = hidden
        self._slot = slot
        self._timeout = timeout
        self._state = False
        self._commands = commands

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

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
    def should_poll(self):
        """We should not be polled for device up state."""
        return False

    @property
    def device_state_attributes(self):
        """Hide remote by default."""
        if self._is_hidden:
            return {'hidden': 'true'}
        return

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGER.error("Device does not support turn_on, "
                      "please use 'remote.send_command' to send commands.")

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.error("Device does not support turn_off, "
                      "please use 'remote.send_command' to send commands.")

    def _send_command(self, payload):
        """Send a command."""
        from miio import DeviceException

        _LOGGER.debug("Sending payload: '%s'", payload)
        try:
            self.device.play(payload)
        except DeviceException as ex:
            _LOGGER.error(
                "Transmit of IR command failed, %s, exception: %s",
                payload, ex)

    def send_command(self, command, **kwargs):
        """Wrapper for _send_command."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS)

        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for payload in command:
                if payload in self._commands:
                    for local_payload in self._commands[payload][CONF_COMMAND]:
                        self._send_command(local_payload)
                else:
                    self._send_command(payload)
                time.sleep(delay)
