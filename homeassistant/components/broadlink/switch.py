"""Support for Broadlink switches."""
from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any

from broadlink.exceptions import BroadlinkException
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_SWITCHES,
    CONF_TIMEOUT,
    CONF_TYPE,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import BroadlinkDevice
from .const import DOMAIN
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

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_SLOTS),
    cv.deprecated(CONF_TIMEOUT),
    cv.deprecated(CONF_TYPE),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_MAC): mac_address,
            vol.Optional(CONF_HOST): cv.string,
            vol.Optional(CONF_SWITCHES, default=[]): vol.All(
                cv.ensure_list,
                [SWITCH_SCHEMA],
            ),
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the device and set up custom switches.

    This is for backward compatibility.
    Do not use this method.
    """
    mac_addr = config[CONF_MAC]
    host = config.get(CONF_HOST)

    if switches := config.get(CONF_SWITCHES):
        platform_data = hass.data[DOMAIN].platforms.get(Platform.SWITCH, {})
        async_add_entities_config_entry: AddEntitiesCallback
        device: BroadlinkDevice
        async_add_entities_config_entry, device = platform_data.get(
            mac_addr, (None, None)
        )
        if not async_add_entities_config_entry:
            raise PlatformNotReady

        async_add_entities_config_entry(
            BroadlinkRMSwitch(device, config) for config in switches
        )

    else:
        _LOGGER.warning(
            "The switch platform is deprecated, except for custom IR/RF "
            "switches. Please refer to the Broadlink documentation to "
            "catch up"
        )

    if host:
        import_device(hass, host)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink switch."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    switches: list[BroadlinkSwitch] = []

    if device.api.type in {"RM4MINI", "RM4PRO", "RMMINI", "RMMINIB", "RMPRO"}:
        platform_data = hass.data[DOMAIN].platforms.setdefault(Platform.SWITCH, {})
        platform_data[device.api.mac] = async_add_entities, device
    elif device.api.type == "SP1":
        switches.append(BroadlinkSP1Switch(device))

    elif device.api.type in {"SP2", "SP2S", "SP3", "SP3S", "SP4", "SP4B"}:
        switches.append(BroadlinkSP2Switch(device))

    elif device.api.type == "BG1":
        switches.extend(BroadlinkBG1Slot(device, slot) for slot in range(1, 3))

    elif device.api.type == "MP1":
        switches.extend(BroadlinkMP1Slot(device, slot) for slot in range(1, 5))

    async_add_entities(switches)


class BroadlinkSwitch(BroadlinkEntity, SwitchEntity, RestoreEntity, ABC):
    """Representation of a Broadlink switch."""

    _attr_assumed_state = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, device, command_on, command_off):
        """Initialize the switch."""
        super().__init__(device)
        self._command_on = command_on
        self._command_off = command_off
        self._attr_name = f"{device.name} Switch"

    async def async_added_to_hass(self) -> None:
        """Call when the switch is added to hass."""
        state = await self.async_get_last_state()
        self._attr_is_on = state is not None and state.state == STATE_ON
        await super().async_added_to_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if await self._async_send_packet(self._command_on):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
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
        device = self._device

        if packet is None:
            return True

        try:
            await device.async_request(device.api.send_data, packet)
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
        device = self._device

        try:
            await device.async_request(device.api.set_power, packet)
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

    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_is_on = data["pwr"]


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

    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_is_on = data[f"s{self._slot}"]

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        device = self._device

        try:
            await device.async_request(device.api.set_power, self._slot, packet)
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
        self._attr_device_class = SwitchDeviceClass.OUTLET
        self._attr_unique_id = f"{device.unique_id}-s{slot}"

    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_is_on = data[f"pwr{self._slot}"]

    async def _async_send_packet(self, packet):
        """Send a packet to the device."""
        device = self._device
        state = {f"pwr{self._slot}": packet}

        try:
            await device.async_request(device.api.set_state, **state)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True
