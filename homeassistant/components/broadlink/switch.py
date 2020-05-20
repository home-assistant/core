"""Support for Broadlink RM devices."""
from datetime import timedelta
from ipaddress import ip_address
import logging

import broadlink as blk
from broadlink.exceptions import BroadlinkException
import voluptuous as vol

from homeassistant.components.switch import DOMAIN, PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_MAC,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_TYPE,
    STATE_ON,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle, slugify

from . import async_setup_service, data_packet, hostname, mac_address
from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    MP1_TYPES,
    RM4_TYPES,
    RM_TYPES,
    SP1_TYPES,
    SP2_TYPES,
)
from .device import BroadlinkDevice

_LOGGER = logging.getLogger(__name__)

TIME_BETWEEN_UPDATES = timedelta(seconds=5)

CONF_SLOTS = "slots"
CONF_RETRY = "retry"

DEVICE_TYPES = RM_TYPES + RM4_TYPES + SP1_TYPES + SP2_TYPES + MP1_TYPES

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_OFF): data_packet,
        vol.Optional(CONF_COMMAND_ON): data_packet,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    }
)

MP1_SWITCH_SLOT_SCHEMA = vol.Schema(
    {
        vol.Optional("slot_1"): cv.string,
        vol.Optional("slot_2"): cv.string,
        vol.Optional("slot_3"): cv.string,
        vol.Optional("slot_4"): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SWITCHES, default={}): cv.schema_with_slug_keys(
            SWITCH_SCHEMA
        ),
        vol.Optional(CONF_SLOTS, default={}): MP1_SWITCH_SLOT_SCHEMA,
        vol.Required(CONF_HOST): vol.All(vol.Any(hostname, ip_address), cv.string),
        vol.Required(CONF_MAC): mac_address,
        vol.Optional(CONF_FRIENDLY_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=DEVICE_TYPES[0]): vol.In(DEVICE_TYPES),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Broadlink switches."""

    host = config[CONF_HOST]
    mac_addr = config[CONF_MAC]
    friendly_name = config[CONF_FRIENDLY_NAME]
    model = config[CONF_TYPE]
    timeout = config[CONF_TIMEOUT]
    slots = config[CONF_SLOTS]
    devices = config[CONF_SWITCHES]

    def generate_rm_switches(switches, broadlink_device):
        """Generate RM switches."""
        return [
            BroadlinkRMSwitch(
                object_id,
                config.get(CONF_FRIENDLY_NAME, object_id),
                broadlink_device,
                config.get(CONF_COMMAND_ON),
                config.get(CONF_COMMAND_OFF),
            )
            for object_id, config in switches.items()
        ]

    def get_mp1_slot_name(switch_friendly_name, slot):
        """Get slot name."""
        if not slots[f"slot_{slot}"]:
            return f"{switch_friendly_name} slot {slot}"
        return slots[f"slot_{slot}"]

    if model in RM_TYPES:
        api = blk.rm((host, DEFAULT_PORT), mac_addr, None)
        broadlink_device = BroadlinkDevice(hass, api)
        switches = generate_rm_switches(devices, broadlink_device)
    elif model in RM4_TYPES:
        api = blk.rm4((host, DEFAULT_PORT), mac_addr, None)
        broadlink_device = BroadlinkDevice(hass, api)
        switches = generate_rm_switches(devices, broadlink_device)
    elif model in SP1_TYPES:
        api = blk.sp1((host, DEFAULT_PORT), mac_addr, None)
        broadlink_device = BroadlinkDevice(hass, api)
        switches = [BroadlinkSP1Switch(friendly_name, broadlink_device)]
    elif model in SP2_TYPES:
        api = blk.sp2((host, DEFAULT_PORT), mac_addr, None)
        broadlink_device = BroadlinkDevice(hass, api)
        switches = [BroadlinkSP2Switch(friendly_name, broadlink_device)]
    elif model in MP1_TYPES:
        api = blk.mp1((host, DEFAULT_PORT), mac_addr, None)
        broadlink_device = BroadlinkDevice(hass, api)
        parent_device = BroadlinkMP1Switch(broadlink_device)
        switches = [
            BroadlinkMP1Slot(
                get_mp1_slot_name(friendly_name, i), broadlink_device, i, parent_device,
            )
            for i in range(1, 5)
        ]

    api.timeout = timeout
    connected = await broadlink_device.async_connect()
    if not connected:
        raise PlatformNotReady

    if model in RM_TYPES or model in RM4_TYPES:
        hass.async_create_task(async_setup_service(hass, host, broadlink_device))

    async_add_entities(switches)


class BroadlinkRMSwitch(SwitchEntity, RestoreEntity):
    """Representation of an Broadlink switch."""

    def __init__(self, name, friendly_name, device, command_on, command_off):
        """Initialize the switch."""
        self.device = device
        self.entity_id = f"{DOMAIN}.{slugify(name)}"
        self._name = friendly_name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._state = state.state == STATE_ON

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def available(self):
        """Return True if entity is available."""
        return not self.should_poll or self.device.available

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_update(self):
        """Update the state of the device."""
        if not self.available:
            await self.device.async_connect()

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if await self._async_send_packet(self._command_on):
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if await self._async_send_packet(self._command_off):
            self._state = False
            self.async_write_ha_state()

    async def _async_send_packet(self, packet):
        """Send packet to device."""
        if packet is None:
            _LOGGER.debug("Empty packet")
            return True
        try:
            await self.device.async_request(self.device.api.send_data, packet)
        except BroadlinkException as err_msg:
            _LOGGER.error("Failed to send packet: %s", err_msg)
            return False
        return True


class BroadlinkSP1Switch(BroadlinkRMSwitch):
    """Representation of an Broadlink switch."""

    def __init__(self, friendly_name, device):
        """Initialize the switch."""
        super().__init__(friendly_name, friendly_name, device, None, None)
        self._command_on = 1
        self._command_off = 0
        self._load_power = None

    async def _async_send_packet(self, packet):
        """Send packet to device."""
        try:
            await self.device.async_request(self.device.api.set_power, packet)
        except BroadlinkException as err_msg:
            _LOGGER.error("Failed to send packet: %s", err_msg)
            return False
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

    @property
    def current_power_w(self):
        """Return the current power usage in Watt."""
        try:
            return round(self._load_power, 2)
        except (ValueError, TypeError):
            return None

    async def async_update(self):
        """Update the state of the device."""
        try:
            state = await self.device.async_request(self.device.api.check_power)
            load_power = await self.device.async_request(self.device.api.get_energy)
        except BroadlinkException as err_msg:
            _LOGGER.error("Failed to update state: %s", err_msg)
            return
        self._state = state
        self._load_power = load_power


class BroadlinkMP1Slot(BroadlinkRMSwitch):
    """Representation of a slot of Broadlink switch."""

    def __init__(self, friendly_name, device, slot, parent_device):
        """Initialize the slot of switch."""
        super().__init__(friendly_name, friendly_name, device, None, None)
        self._command_on = 1
        self._command_off = 0
        self._slot = slot
        self._parent_device = parent_device

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return False

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    async def async_update(self):
        """Update the state of the device."""
        await self._parent_device.async_update()
        self._state = self._parent_device.get_outlet_status(self._slot)

    async def _async_send_packet(self, packet):
        """Send packet to device."""
        try:
            await self.device.async_request(
                self.device.api.set_power, self._slot, packet
            )
        except BroadlinkException as err_msg:
            _LOGGER.error("Failed to send packet: %s", err_msg)
            return False
        return True


class BroadlinkMP1Switch:
    """Representation of a Broadlink switch - To fetch states of all slots."""

    def __init__(self, device):
        """Initialize the switch."""
        self.device = device
        self._states = None

    def get_outlet_status(self, slot):
        """Get status of outlet from cached status list."""
        if self._states is None:
            return None
        return self._states[f"s{slot}"]

    @Throttle(TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update the state of the device."""
        try:
            states = await self.device.async_request(self.device.api.check_power)
        except BroadlinkException as err_msg:
            _LOGGER.error("Failed to update state: %s", err_msg)
        self._states = states
