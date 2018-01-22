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
    CONF_SWITCHES, CONF_HOST, CONF_TOKEN)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

REQUIREMENTS = ['python-miio==0.3.4']

_LOGGER = logging.getLogger(__name__)

SERVICE_LEARN = 'chuangmiIr_learn_command'
SERVICE_SEND = 'chuangmiIr_send_packet'

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMAND_OFF, default=None): cv.string,
    vol.Optional(CONF_COMMAND_ON, default=None): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_SWITCHES, default={}):
        vol.Schema({cv.slug: SWITCH_SCHEMA}),
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Xiaomi IR Remote (Chuangmi IR) platform."""
    from miio import ChuangmiIr, DeviceException
    from construct import ChecksumError

    @asyncio.coroutine
    def _learn_command(call):
        """Handle a learn command."""
        from random import randint
        slot = randint(1, 1000000)

        yield from hass.async_add_job(remote.learn, slot)

        _LOGGER.info("Press the key you want Home Assistant to learn")
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=20):
            packet = yield from hass.async_add_job(
                remote.read, slot)
            if packet['code']:
                log_msg = "Recieved packet is: {}".\
                          format(packet['code'])
                _LOGGER.info(log_msg)
                hass.components.persistent_notification.async_create(
                    log_msg, title='ChuangmiIr')
                return
            yield from asyncio.sleep(1, loop=hass.loop)
        _LOGGER.error("Did not received any signal")
        hass.components.persistent_notification.async_create(
            "Did not received any signal", title='ChuangmiIr')

    @asyncio.coroutine
    def _send_packet(call):
        """Send a packet."""
        packets = call.data.get('packet', [])
        for packet in packets:
            payload = str(packet)
            _LOGGER.debug(payload)
            try:
                yield from hass.async_add_job(
                    remote.play, payload, None)
            except DeviceException as ex:
                _LOGGER.error(
                    "Failed to send packet, %s, exception: %s", payload, ex)

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
    remote = ChuangmiIr(host, token)

    try:
        remote.info()
    except ChecksumError as ex:
        _LOGGER.error("Token is wrong : %s", ex)
        return

    hass.services.register(DOMAIN, SERVICE_LEARN + '_' +
                           host.replace('.', '_'), _learn_command)
    hass.services.register(DOMAIN, SERVICE_SEND + '_' +
                           host.replace('.', '_'), _send_packet)

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
    add_devices(switches)


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
        success = yield from self._sendpacket(self._command_on)
        if success:
            self._state = True
            self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        success = yield from self._sendpacket(self._command_off)
        if success:
            self._state = False
            self.schedule_update_ha_state()

    @asyncio.coroutine
    def _sendpacket(self, packet):
        """Send packet to device."""
        from miio import DeviceException

        if packet is None:
            _LOGGER.debug("Empty packet")
            return True
        try:
            yield from self.hass.async_add_job(
                self._device.play, packet, None)
        except DeviceException as exc:
            _LOGGER.error(exc)
            return False
        return True
