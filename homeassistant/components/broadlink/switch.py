"""Support for Broadlink switches."""
from abc import ABC, abstractmethod
from functools import partial
import logging

from broadlink.exceptions import BroadlinkException
import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    DEVICE_CLASS_SWITCH,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_TYPE,
    STATE_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SWITCH_DOMAIN
from .entity import BroadlinkEntity
from .helpers import data_packet, import_device, mac_address

_LOGGER = logging.getLogger(__name__)

CONF_SLOTS = "slots"

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_COMMAND_OFF): data_packet,
        vol.Optional(CONF_COMMAND_ON): data_packet,
    }
)

OLD_SWITCH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_OFF): data_packet,
        vol.Optional(CONF_COMMAND_ON): data_packet,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_SLOTS),
    cv.deprecated(CONF_TIMEOUT),
    cv.deprecated(CONF_TYPE),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_MAC): mac_address,
            vol.Optional(CONF_HOST): cv.string,
            vol.Optional(CONF_SWITCHES, default=[]): vol.Any(
                cv.schema_with_slug_keys(OLD_SWITCH_SCHEMA),
                vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
            ),
        }
    ),
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the device and set up custom switches.

    This is for backward compatibility.
    Do not use this method.
    """
    mac_addr = config[CONF_MAC]
    host = config.get(CONF_HOST)
    switches = config.get(CONF_SWITCHES)

    if not isinstance(switches, list):
        switches = [
            {CONF_NAME: switch.pop(CONF_FRIENDLY_NAME, name), **switch}
            for name, switch in switches.items()
        ]

        _LOGGER.warning(
            "Your configuration for the switch platform is deprecated. "
            "Please refer to the Broadlink documentation to catch up"
        )

    if switches:
        platform_data = hass.data[DOMAIN].platforms.setdefault(SWITCH_DOMAIN, {})
        platform_data.setdefault(mac_addr, []).extend(switches)

    else:
        _LOGGER.warning(
            "The switch platform is deprecated, except for custom IR/RF "
            "switches. Please refer to the Broadlink documentation to "
            "catch up"
        )

    if host:
        import_device(hass, host)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink switch."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    if device.api.type in {"RM4MINI", "RM4PRO", "RMMINI", "RMMINIB", "RMPRO"}:
        platform_data = hass.data[DOMAIN].platforms.get(SWITCH_DOMAIN, {})
        user_defined_switches = platform_data.get(device.api.mac, {})
        switches = [
            BroadlinkRMSwitch(device, config) for config in user_defined_switches
        ]

    elif device.api.type == "SP1":
        switches = [BroadlinkSP1Switch(device)]

    elif device.api.type in {"SP2", "SP2S", "SP3", "SP3S", "SP4", "SP4B"}:
        switches = [BroadlinkSP2Switch(device)]

    elif device.api.type == "BG1":
        switches = [BroadlinkBG1Slot(device, slot) for slot in range(1, 3)]

    elif device.api.type == "MP1":
        switches = [BroadlinkMP1Slot(device, slot) for slot in range(1, 5)]

    async_add_entities(switches)


class BroadlinkSwitch(BroadlinkEntity, SwitchEntity, RestoreEntity, ABC):
    """Representation of a Broadlink switch."""

    _attr_assumed_state = True
    _attr_device_class = DEVICE_CLASS_SWITCH

    def __init__(self, device, command_on, command_off):
        """Initialize the switch."""
        super().__init__(device)
        self._command_on = command_on
        self._command_off = command_off
        self._coordinator = device.update_manager.coordinator

        self._attr_assumed_state = True
        self._attr_device_class = DEVICE_CLASS_SWITCH
        self._attr_name = f"{device.name} Switch"
        self._attr_unique_id = device.unique_id

    @callback
    def update_data(self):
        """Update data."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the switch is added to hass."""
        state = await self.async_get_last_state()
        self._attr_is_on = state is not None and state.state == STATE_ON
        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the switch."""
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        if await self._async_send_packet(self._command_on):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        if await self._async_send_packet(self._command_off):
            self._attr_is_on = False
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
        self._attr_name = config[CONF_NAME]

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        if packet is None:
            return True

        try:
            await self._device.async_request(self._device.api.send_data, packet)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkSP1Switch(BroadlinkSwitch):
    """Representation of a Broadlink SP1 switch."""

    def __init__(self, device):
        """Initialize the switch."""
        super().__init__(device, 1, 0)
        self._attr_unique_id = self._device.unique_id

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        try:
            await self._device.async_request(self._device.api.set_power, packet)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkSP2Switch(BroadlinkSP1Switch):
    """Representation of a Broadlink SP2 switch."""

    _attr_assumed_state = False

    def __init__(self, device, *args, **kwargs):
        """Initialize the switch."""
        super().__init__(device, *args, **kwargs)
        self._attr_is_on = self._coordinator.data["pwr"]
        self._attr_current_power_w = self._coordinator.data.get("power")

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            self._attr_is_on = self._coordinator.data["pwr"]
            self._attr_current_power_w = self._coordinator.data.get("power")
        self.async_write_ha_state()


class BroadlinkMP1Slot(BroadlinkSwitch):
    """Representation of a Broadlink MP1 slot."""

    _attr_assumed_state = False

    def __init__(self, device, slot):
        """Initialize the switch."""
        super().__init__(device, 1, 0)
        self._slot = slot
        self._attr_is_on = self._coordinator.data[f"s{slot}"]
        self._attr_name = f"{device.name} S{slot}"
        self._attr_unique_id = f"{device.unique_id}-s{slot}"

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            self._attr_is_on = self._coordinator.data[f"s{self._slot}"]
        self.async_write_ha_state()

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        try:
            await self._device.async_request(
                self._device.api.set_power, self._slot, packet
            )
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True


class BroadlinkBG1Slot(BroadlinkSwitch):
    """Representation of a Broadlink BG1 slot."""

    _attr_assumed_state = False

    def __init__(self, device, slot):
        """Initialize the switch."""
        super().__init__(device, 1, 0)
        self._slot = slot
        self._attr_is_on = self._coordinator.data[f"pwr{slot}"]

        self._attr_name = f"{device.name} S{slot}"
        self._attr_device_class = DEVICE_CLASS_OUTLET
        self._attr_unique_id = f"{device.unique_id}-s{slot}"

    @callback
    def update_data(self):
        """Update data."""
        if self._coordinator.last_update_success:
            self._attr_is_on = self._coordinator.data[f"pwr{self._slot}"]
        self.async_write_ha_state()

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        set_state = partial(self._device.api.set_state, **{f"pwr{self._slot}": packet})
        try:
            await self._device.async_request(set_state)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True
