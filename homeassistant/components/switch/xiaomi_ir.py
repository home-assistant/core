"""
Support for the Xiaomi IR Remote (Chuangmi IR).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ir_remote.xiaomi_miio/
"""
import asyncio
import logging

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.switch import (
    DOMAIN, PLATFORM_SCHEMA, SwitchDevice)
from homeassistant.const import (
    CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_FRIENDLY_NAME,
    CONF_SWITCHES, CONF_HOST, CONF_TOKEN, CONF_SLOT, CONF_TIMEOUT)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

REQUIREMENTS = ['python-miio==0.3.4']

_LOGGER = logging.getLogger(__name__)

SERVICE_LEARN = 'xiaomi_miio_learn_command'
SERVICE_SEND = 'xiaomi_miio_send_command'

DEFAULT_TIMEOUT = 10
DEFAULT_SLOT = 1

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMAND_OFF, default=None): cv.string,
    vol.Optional(CONF_COMMAND_ON, default=None): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
})

LEARN_COMMAND_SCHEMA = vol.Schema({
    vol.Optional("timeout", default=10):
        vol.All(int, vol.Range(min=0)),
    vol.Optional("slot", default=1):
        vol.All(int, vol.Range(min=1, max=1000000)),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_SWITCHES, default={}):
        vol.Schema({cv.slug: SWITCH_SCHEMA}),
}, extra=vol.ALLOW_EXTRA).extend(LEARN_COMMAND_SCHEMA.schema)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Xiaomi IR Remote (Chuangmi IR) platform."""
    from miio import ChuangmiIr, DeviceException
    from construct import ChecksumError

    @asyncio.coroutine
    def _learn_command(call):
        """Handle a learn command."""
        slot = int(call.data.get('slot', config.get(CONF_SLOT)))

        yield from hass.async_add_job(remote.learn, slot)

        timeout = int(call.data.get('timeout', config.get(CONF_TIMEOUT)))

        _LOGGER.info("Press the key you want Home Assistant to learn")
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=timeout):
            packet = yield from hass.async_add_job(
                remote.read, slot)
            if packet['code']:
                log_msg = "Received command is: {}".\
                          format(packet['code'])
                _LOGGER.info(log_msg)
                hass.components.persistent_notification.async_create(
                    log_msg, title='Xiaomi IR Remote Controller')
                return
            yield from asyncio.sleep(1, loop=hass.loop)
        _LOGGER.error("Timeout. No infrared command captured")
        hass.components.persistent_notification.async_create(
            "Timeout. No infrared command captured",
            title='Xiaomi IR Remote Controller')

    @asyncio.coroutine
    def _send_command(call):
        """Send a packet."""
        packets = call.data.get('command', [])
        for packet in packets:
            payload = str(packet)
            _LOGGER.debug(payload)
            try:
                yield from hass.async_add_job(
                    remote.play, payload, None)
            except DeviceException as ex:
                _LOGGER.error(
                    "Transmit of IR command failed, %s, exception: %s",
                    payload, ex)

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
    remote = ChuangmiIr(host, token)

    try:
        remote.info()
    except ChecksumError as ex:
        _LOGGER.error("Token not accepted by device : %s", ex)
        return

    hass.services.async_register(DOMAIN, SERVICE_LEARN + '_' +
                                 host.replace('.', '_'), _learn_command,
                                 schema=LEARN_COMMAND_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SEND + '_' +
                                 host.replace('.', '_'), _send_command)

    devices = config.get(CONF_SWITCHES)

    switches = []
    for object_id, device_config in devices.items():
        switches.append(
            ChuangmiIrSwitch(
                device_config.get(CONF_FRIENDLY_NAME, object_id),
                remote,
                device_config.get(CONF_COMMAND_ON),
                device_config.get(CONF_COMMAND_OFF)
            )
        )
    async_add_devices(switches)


class ChuangmiIrSwitch(SwitchDevice):
    """Representation of a ChuangmiIr switch."""

    def __init__(self, friendly_name, device, command_on, command_off):
        """Initialize the switch."""
        self._name = friendly_name
        self._state = False
        self._command_on = command_on if command_on else None
        self._command_off = command_off if command_off else None
        self._device = device

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        success = yield from self._sendcommand(self._command_on)
        if success:
            self._state = True
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        success = yield from self._sendcommand(self._command_off)
        if success:
            self._state = False
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def _sendcommand(self, command):
        """Send packet to device."""
        from miio import DeviceException

        if command is None:
            _LOGGER.debug("Empty infrared command skipped.")
            return True
        try:
            yield from self.hass.async_add_job(
                self._device.play, command, None)
        except DeviceException as ex:
            _LOGGER.error(ex)
            return False
        return True
