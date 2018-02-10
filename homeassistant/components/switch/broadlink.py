"""
Support for Broadlink RM devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.broadlink/
"""
import asyncio
from base64 import b64decode, b64encode
import binascii
from datetime import timedelta
import logging
import socket

import voluptuous as vol

from homeassistant.components.switch import (
    DOMAIN, PLATFORM_SCHEMA, SwitchDevice)
from homeassistant.const import (
    CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_FRIENDLY_NAME, CONF_HOST, CONF_MAC,
    CONF_SWITCHES, CONF_TIMEOUT, CONF_TYPE)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

REQUIREMENTS = ['broadlink==0.5']

_LOGGER = logging.getLogger(__name__)

TIME_BETWEEN_UPDATES = timedelta(seconds=5)

DEFAULT_NAME = 'Broadlink switch'
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3
SERVICE_LEARN = 'broadlink_learn_command'
SERVICE_SEND = 'broadlink_send_packet'
CONF_SLOTS = 'slots'

RM_TYPES = ['rm', 'rm2', 'rm_mini', 'rm_pro_phicomm', 'rm2_home_plus',
            'rm2_home_plus_gdt', 'rm2_pro_plus', 'rm2_pro_plus2',
            'rm2_pro_plus_bl', 'rm_mini_shate']
SP1_TYPES = ['sp1']
SP2_TYPES = ['sp2', 'honeywell_sp2', 'sp3', 'spmini2', 'spminiplus']
MP1_TYPES = ['mp1']

SWITCH_TYPES = RM_TYPES + SP1_TYPES + SP2_TYPES + MP1_TYPES

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMAND_OFF, default=None): cv.string,
    vol.Optional(CONF_COMMAND_ON, default=None): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
})

MP1_SWITCH_SLOT_SCHEMA = vol.Schema({
    vol.Optional('slot_1'): cv.string,
    vol.Optional('slot_2'): cv.string,
    vol.Optional('slot_3'): cv.string,
    vol.Optional('slot_4'): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SWITCHES, default={}):
        vol.Schema({cv.slug: SWITCH_SCHEMA}),
    vol.Optional(CONF_SLOTS, default={}): MP1_SWITCH_SLOT_SCHEMA,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TYPE, default=SWITCH_TYPES[0]): vol.In(SWITCH_TYPES),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Broadlink switches."""
    import broadlink
    devices = config.get(CONF_SWITCHES)
    slots = config.get('slots', {})
    ip_addr = config.get(CONF_HOST)
    friendly_name = config.get(CONF_FRIENDLY_NAME)
    mac_addr = binascii.unhexlify(
        config.get(CONF_MAC).encode().replace(b':', b''))
    switch_type = config.get(CONF_TYPE)

    @asyncio.coroutine
    def _learn_command(call):
        """Handle a learn command."""
        try:
            auth = yield from hass.async_add_job(broadlink_device.auth)
        except socket.timeout:
            _LOGGER.error("Failed to connect to device, timeout")
            return
        if not auth:
            _LOGGER.error("Failed to connect to device")
            return

        yield from hass.async_add_job(broadlink_device.enter_learning)

        _LOGGER.info("Press the key you want Home Assistant to learn")
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=20):
            packet = yield from hass.async_add_job(
                broadlink_device.check_data)
            if packet:
                log_msg = "Received packet is: {}".\
                          format(b64encode(packet).decode('utf8'))
                _LOGGER.info(log_msg)
                hass.components.persistent_notification.async_create(
                    log_msg, title='Broadlink switch')
                return
            yield from asyncio.sleep(1, loop=hass.loop)
        _LOGGER.error("Did not received any signal")
        hass.components.persistent_notification.async_create(
            "Did not received any signal", title='Broadlink switch')

    @asyncio.coroutine
    def _send_packet(call):
        """Send a packet."""
        packets = call.data.get('packet', [])
        for packet in packets:
            for retry in range(DEFAULT_RETRY):
                try:
                    extra = len(packet) % 4
                    if extra > 0:
                        packet = packet + ('=' * (4 - extra))
                    payload = b64decode(packet)
                    yield from hass.async_add_job(
                        broadlink_device.send_data, payload)
                    break
                except (socket.timeout, ValueError):
                    try:
                        yield from hass.async_add_job(
                            broadlink_device.auth)
                    except socket.timeout:
                        if retry == DEFAULT_RETRY-1:
                            _LOGGER.error("Failed to send packet to device")

    def _get_mp1_slot_name(switch_friendly_name, slot):
        """Get slot name."""
        if not slots['slot_{}'.format(slot)]:
            return '{} slot {}'.format(switch_friendly_name, slot)
        return slots['slot_{}'.format(slot)]

    if switch_type in RM_TYPES:
        broadlink_device = broadlink.rm((ip_addr, 80), mac_addr)
        hass.services.register(DOMAIN, SERVICE_LEARN + '_' +
                               ip_addr.replace('.', '_'), _learn_command)
        hass.services.register(DOMAIN, SERVICE_SEND + '_' +
                               ip_addr.replace('.', '_'), _send_packet,
                               vol.Schema({'packet': cv.ensure_list}))
        switches = []
        for object_id, device_config in devices.items():
            switches.append(
                BroadlinkRMSwitch(
                    device_config.get(CONF_FRIENDLY_NAME, object_id),
                    broadlink_device,
                    device_config.get(CONF_COMMAND_ON),
                    device_config.get(CONF_COMMAND_OFF)
                )
            )
    elif switch_type in SP1_TYPES:
        broadlink_device = broadlink.sp1((ip_addr, 80), mac_addr)
        switches = [BroadlinkSP1Switch(friendly_name, broadlink_device)]
    elif switch_type in SP2_TYPES:
        broadlink_device = broadlink.sp2((ip_addr, 80), mac_addr)
        switches = [BroadlinkSP2Switch(friendly_name, broadlink_device)]
    elif switch_type in MP1_TYPES:
        switches = []
        broadlink_device = broadlink.mp1((ip_addr, 80), mac_addr)
        parent_device = BroadlinkMP1Switch(broadlink_device)
        for i in range(1, 5):
            slot = BroadlinkMP1Slot(
                _get_mp1_slot_name(friendly_name, i),
                broadlink_device, i, parent_device)
            switches.append(slot)

    broadlink_device.timeout = config.get(CONF_TIMEOUT)
    try:
        broadlink_device.auth()
    except socket.timeout:
        _LOGGER.error("Failed to connect to device")

    add_devices(switches)


class BroadlinkRMSwitch(SwitchDevice):
    """Representation of an Broadlink switch."""

    def __init__(self, friendly_name, device, command_on, command_off):
        """Initialize the switch."""
        self._name = friendly_name
        self._state = False
        self._command_on = b64decode(command_on) if command_on else None
        self._command_off = b64decode(command_off) if command_off else None
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

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if self._sendpacket(self._command_on):
            self._state = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._sendpacket(self._command_off):
            self._state = False
            self.schedule_update_ha_state()

    def _sendpacket(self, packet, retry=2):
        """Send packet to device."""
        if packet is None:
            _LOGGER.debug("Empty packet")
            return True
        try:
            self._device.send_data(packet)
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return False
            if not self._auth():
                return False
            return self._sendpacket(packet, retry-1)
        return True

    def _auth(self, retry=2):
        try:
            auth = self._device.auth()
        except socket.timeout:
            auth = False
        if not auth and retry > 0:
            return self._auth(retry-1)
        return auth


class BroadlinkSP1Switch(BroadlinkRMSwitch):
    """Representation of an Broadlink switch."""

    def __init__(self, friendly_name, device):
        """Initialize the switch."""
        super().__init__(friendly_name, device, None, None)
        self._command_on = 1
        self._command_off = 0

    def _sendpacket(self, packet, retry=2):
        """Send packet to device."""
        try:
            self._device.set_power(packet)
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return False
            if not self._auth():
                return False
            return self._sendpacket(packet, retry-1)
        return True


class BroadlinkSP2Switch(BroadlinkSP1Switch):
    """Representation of an Broadlink switch."""

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return False

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def update(self):
        """Synchronize state with switch."""
        self._update()

    def _update(self, retry=2):
        """Update the state of the device."""
        try:
            state = self._device.check_power()
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return
            if not self._auth():
                return
            return self._update(retry-1)
        if state is None and retry > 0:
            return self._update(retry-1)
        self._state = state


class BroadlinkMP1Slot(BroadlinkRMSwitch):
    """Representation of a slot of Broadlink switch."""

    def __init__(self, friendly_name, device, slot, parent_device):
        """Initialize the slot of switch."""
        super().__init__(friendly_name, device, None, None)
        self._command_on = 1
        self._command_off = 0
        self._slot = slot
        self._parent_device = parent_device

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return False

    def _sendpacket(self, packet, retry=2):
        """Send packet to device."""
        try:
            self._device.set_power(self._slot, packet)
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return False
            if not self._auth():
                return False
            return self._sendpacket(packet, max(0, retry-1))
        return True

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def update(self):
        """Trigger update for all switches on the parent device."""
        self._parent_device.update()
        self._state = self._parent_device.get_outlet_status(self._slot)


class BroadlinkMP1Switch(object):
    """Representation of a Broadlink switch - To fetch states of all slots."""

    def __init__(self, device):
        """Initialize the switch."""
        self._device = device
        self._states = None

    def get_outlet_status(self, slot):
        """Get status of outlet from cached status list."""
        return self._states['s{}'.format(slot)]

    @Throttle(TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for this device."""
        self._update()

    def _update(self, retry=2):
        """Update the state of the device."""
        try:
            states = self._device.check_power()
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return
            if not self._auth():
                return
            return self._update(max(0, retry-1))
        if states is None and retry > 0:
            return self._update(max(0, retry-1))
        self._states = states

    def _auth(self, retry=2):
        """Authenticate the device."""
        try:
            auth = self._device.auth()
        except socket.timeout:
            auth = False
        if not auth and retry > 0:
            return self._auth(retry-1)
        return auth
