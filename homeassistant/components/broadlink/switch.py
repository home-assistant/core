"""Support for Broadlink switches."""
from abc import ABC, abstractmethod
import logging

from broadlink.exceptions import BroadlinkException
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_MAC,
    CONF_NAME,
    CONF_SWITCHES,
    STATE_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SWITCH_DOMAIN
from .helpers import data_packet, mac_address

_LOGGER = logging.getLogger(__name__)

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_COMMAND_OFF): data_packet,
        vol.Optional(CONF_COMMAND_ON): data_packet,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): mac_address,
        vol.Required(CONF_SWITCHES, default=[]): vol.All(
            [SWITCH_SCHEMA], cv.ensure_list
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Broadlink switches."""
    platform_data = hass.data[DOMAIN].platforms.setdefault(SWITCH_DOMAIN, {})
    platform_data.setdefault(config[CONF_MAC], []).extend(config[CONF_SWITCHES])


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink switch."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    if device.api.type in {"RM2", "RM4"}:
        platform_data = hass.data[DOMAIN].platforms.get(SWITCH_DOMAIN, {})
        user_defined_switches = platform_data.get(device.api.mac, {})
        switches = [
            BroadlinkRMSwitch(device, config) for config in user_defined_switches
        ]

    elif device.api.type == "SP1":
        switches = [BroadlinkSP1Switch(device)]

    elif device.api.type == "SP2":
        switches = [BroadlinkSP2Switch(device)]

    elif device.api.type == "MP1":
        switches = [BroadlinkMP1Slot(device, slot) for slot in range(1, 5)]

    async_add_entities(switches)


class BroadlinkSwitch(SwitchEntity, RestoreEntity, ABC):
    """Representation of a Broadlink switch."""

    def __init__(self, device, command_on, command_off):
        """Initialize the switch."""
        self._device = device
        self._command_on = command_on
        self._command_off = command_off
        self._coordinator = device.update_manager.coordinator
        self._state = None

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._device.name} Switch"

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the switch."""
        return True

    @property
    def available(self):
        """Return True if the switch is available."""
        return self._device.update_manager.available

    @property
    def is_on(self):
        """Return True if the switch is on."""
        return self._state

    @property
    def should_poll(self):
        """Return True if the switch has to be polled for state."""
        return False

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "manufacturer": self._device.api.manufacturer,
            "model": self._device.api.model,
            "name": self._device.name,
            "sw_version": self._device.fw_version,
        }

    @callback
    def update_data(self):
        """Update data."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the switch is added to hass."""
        if self._state is None:
            state = await self.async_get_last_state()
            self._state = state is not None and state.state == STATE_ON
        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the switch."""
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        if await self._async_send_packet(self._command_on):
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        if await self._async_send_packet(self._command_off):
            self._state = False
            self.async_write_ha_state()

    @abstractmethod
    async def _async_send_packet(self, packet):
        """Send a packet to the device."""


class BroadlinkRMSwitch(BroadlinkSwitch):
    """Representation of a Broadlink RM switch."""

    def __init__(self, device, config):
        """Initialize the switch."""
        super().__init__(
            device, config.get(CONF_COMMAND_ON), config.get(CONF_COMMAND_OFF)
        )
        self._name = config[CONF_NAME]

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        if packet is None:
            return True

        try:
            await self._device.async_request(self._device.api.send_data, packet)
        except BroadlinkException as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkSP1Switch(BroadlinkSwitch):
    """Representation of a Broadlink SP1 switch."""

    def __init__(self, device):
        """Initialize the switch."""
        super().__init__(device, 1, 0)

    @property
    def unique_id(self):
        """Return the unique id of the switch."""
        return self._device.unique_id

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        try:
            await self._device.async_request(self._device.api.set_power, packet)
        except BroadlinkException as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkSP2Switch(BroadlinkSP1Switch):
    """Representation of a Broadlink SP2 switch."""

    def __init__(self, *args, **kwargs):
        """Initialize the switch."""
        super().__init__(*args, **kwargs)
        self._state = self._coordinator.data["state"]
        self._load_power = self._coordinator.data["load_power"]

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the switch."""
        return False

    @property
    def current_power_w(self):
        """Return the current power usage in Watt."""
        return self._load_power

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            self._state = self._coordinator.data["state"]
            self._load_power = self._coordinator.data["load_power"]
        self.async_write_ha_state()


class BroadlinkMP1Slot(BroadlinkSwitch):
    """Representation of a Broadlink MP1 slot."""

    def __init__(self, device, slot):
        """Initialize the switch."""
        super().__init__(device, 1, 0)
        self._slot = slot
        self._state = self._coordinator.data[f"s{slot}"]

    @property
    def unique_id(self):
        """Return the unique id of the slot."""
        return f"{self._device.unique_id}-slot-{self._slot}"

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._device.name} Slot {self._slot}"

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the switch."""
        return False

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            self._state = self._coordinator.data[f"s{self._slot}"]
        self.async_write_ha_state()

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        try:
            await self._device.async_request(
                self._device.api.set_power, self._slot, packet
            )
        except BroadlinkException as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True
