"""Home Assistant Switcher Component.

For controlling the Switcher Boiler Device (https://www.switcher.co.il/).
Please follow configuring instryctuins here: fill-in-here.

For pylint's incorrectly reports of no 'getLogger' in module 'logging':
- Disabled pylint's 'E0611' (no-name-in-module) warning.

Author: Tomer Figenblat

This cannot be configured as a sensor platform,
Please follow the instruction of configuring the switcher_kis component.
"""

# pylint: disable=no-name-in-module
from asyncio import TimeoutError as AsyncioTimeoutError
from asyncio import wait_for
from datetime import datetime
from functools import partial
from logging import getLogger
from typing import Any, Awaitable, Callable, Dict, Optional

from aioswitcher.consts import COMMAND_OFF, COMMAND_ON
from aioswitcher.consts import STATE_OFF as SWITCHER_STATE_OFF
from aioswitcher.consts import STATE_ON as SWITCHER_STATE_ON
from aioswitcher.devices import SwitcherV2Device
from aioswitcher.swapi import send_command_to_device

from homeassistant.components.switch import ATTR_CURRENT_POWER_W
from homeassistant.components.switch import ENTITY_ID_FORMAT as SWITCH_FORMAT
from homeassistant.components.switch import SwitchDevice
from homeassistant.components.switcher_kis import (DISCOVERY_CONFIG,
                                                   DISCOVERY_DEVICE)
from homeassistant.components.switcher_kis import \
    ENTITY_ID_FORMAT as SWITCHER_KIS_FORMAT
from homeassistant.components.switcher_kis import async_register_switch_entity
from homeassistant.const import (CONF_FRIENDLY_NAME, CONF_ICON, CONF_NAME,
                                 STATE_OFF, STATE_ON, STATE_UNKNOWN)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import async_generate_entity_id

DEPENDENCIES = ['switcher_kis']

_LOGGER = getLogger(__name__)

ENTITY_ID_FORMAT = SWITCH_FORMAT.format(SWITCHER_KIS_FORMAT)

ATTR_IP_ADDRESS = 'ip_address'
ATTR_ELECTRIC_CURRNET = 'electric_current'
ATTR_REMAINING_TIME = 'remaining_time'
ATTR_AUTO_OFF_SET = 'auto_off_set'
ATTR_LAST_DATA_UPDATE = 'last_data_update'
ATTR_LAST_STATE_CHANGE = 'last_state_change'
ATTR_DEVICE_NAME = 'device_name'

PROPERTIES_TO_ATTRIBUTES = {
    'current_power_w': ATTR_CURRENT_POWER_W,
    'device_ip_addr': ATTR_IP_ADDRESS,
    'electric_current': ATTR_ELECTRIC_CURRNET,
    'remaining_time': ATTR_REMAINING_TIME,
    'auto_off_set': ATTR_AUTO_OFF_SET,
    'last_data_update': ATTR_LAST_DATA_UPDATE,
    'last_state_change': ATTR_LAST_STATE_CHANGE,
    'device_name': ATTR_DEVICE_NAME
}


async def async_setup_platform(hass: HomeAssistant, config: Dict,
                               async_add_entities: Callable,
                               discovery_info: Dict) -> None:
    """Set up the switcher platform for the switch component."""
    if discovery_info.get(DISCOVERY_CONFIG):
        name = str(discovery_info[DISCOVERY_CONFIG].get(CONF_NAME))

        friendly_name = discovery_info[DISCOVERY_CONFIG].get(
            CONF_FRIENDLY_NAME, name.title())

        icon = discovery_info[DISCOVERY_CONFIG].get(CONF_ICON)

    else:
        raise PlatformNotReady("No config data found")

    if discovery_info.get(DISCOVERY_DEVICE):
        switcher_entity = SwitcherControl(hass, name, friendly_name, icon,
                                          discovery_info.get(DISCOVERY_DEVICE))

    else:
        raise PlatformNotReady("No device data discoverd")

    async_add_entities([switcher_entity], False)

    try:
        await wait_for(async_register_switch_entity(switcher_entity),
                       timeout=1)

    except AsyncioTimeoutError:
        raise PlatformNotReady("Unable to register for data updates")

    return None


class SwitcherControl(SwitchDevice):
    """Home Assistant entity.

    Data updates is handled by the bridge thread,
    Therefore no polling by ha is needed.
    """

    def __init__(self, hass: HomeAssistant, name: str, friendly_name: str,
                 icon: Optional[str], device_data: SwitcherV2Device) -> None:
        """Initialize the entity."""
        self._hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, name, hass=hass)
        self._name = friendly_name
        self._icon = icon
        self._self_initiated = False

        self._device_data = device_data
        self._state = device_data.state

    @property
    def device_ip_addr(self) -> str:
        """Return the device's ip address."""
        ret = self._device_data.ip_addr  # type: str
        return ret

    @property
    def electric_current(self) -> Optional[float]:
        """Return the electric current."""
        ret = self._device_data.electric_current  # type: Optional[float]
        return ret

    @property
    def remaining_time(self) -> Optional[str]:
        """Return the remaining time to off command."""
        ret = self._device_data.remaining_time  # type: Optional[str]
        return ret

    @property
    def auto_off_set(self) -> str:
        """Return the auto off configuration set."""
        ret = self._device_data.auto_off_set  # type: str
        return ret

    @property
    def last_data_update(self) -> datetime:
        """Return the datetime for the last update received by the device."""
        ret = self._device_data.last_data_update  # type: datetime
        return ret

    @property
    def last_state_change(self) -> datetime:
        """Return the datetime for the last state change."""
        ret = self._device_data.last_state_change  # type: datetime
        return ret

    @property
    def device_name(self) -> str:
        """Return the device's name."""
        ret = self._device_data.name  # type: str
        return ret

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}-{}".format(
            self._device_data.device_id, self._device_data.mac_addr)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return (
            STATE_ON if self._state == SWITCHER_STATE_ON
            else STATE_OFF if self._state == SWITCHER_STATE_OFF
            else STATE_UNKNOWN)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.state == STATE_ON

    @property
    def current_power_w(self) -> Optional[int]:
        """Return the current power usage in W."""
        ret = self._device_data.power_consumption  # type: Optional[int]
        return ret

    @property
    def state_attributes(self) -> Dict:
        """Return the optional state attributes."""
        attribs = {}

        for prop, attr in PROPERTIES_TO_ATTRIBUTES.items():
            value = getattr(self, prop)
            if value:
                attribs[attr] = value

        return attribs

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return not self.state == STATE_UNKNOWN

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return False

    async def async_update_data(self, device_data: SwitcherV2Device) -> None:
        """Update the entity data.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._self_initiated:
            self._self_initiated = False
        else:
            self._device_data = device_data
            self._state = self._device_data.state
            await self._hass.async_create_task(self.async_update_ha_state())

        return None

    def turn_on(self, **kwargs: Dict) -> None:
        """Turn the entity on."""
        self._hass.async_add_job(partial(self.async_turn_on, **kwargs))

    async def async_turn_on(self, **kwargs: Dict) -> None:
        """Turn the entity on.

        This method must be run in the event loop and returns a coroutine.
        """
        response = await send_command_to_device(
            self.device_ip_addr, self._device_data.phone_id,
            self._device_data.device_id, self._device_data.device_password,
            COMMAND_ON)

        if response.successful:
            self._self_initiated = True
            self._state = STATE_ON
            await self._hass.async_create_task(self.async_update_ha_state())

        return None

    def turn_off(self, **kwargs: Dict) -> None:
        """Turn the entity off."""
        self._hass.async_add_job(partial(self.async_turn_off, **kwargs))

    async def async_turn_off(self, **kwargs: Dict) -> None:
        """Turn the entity off.

        This method must be run in the event loop and returns a coroutine.
        """
        response = await send_command_to_device(
            self.device_ip_addr, self._device_data.phone_id,
            self._device_data.device_id, self._device_data.device_password,
            COMMAND_OFF)

        if response.successful:
            self._self_initiated = True
            self._state = STATE_OFF
            await self._hass.async_create_task(self.async_update_ha_state())

        return None

    def toggle(self, **kwargs: Dict) -> None:
        """Toggle the entity."""
        if self.is_on:
            return self.turn_off(**kwargs)
        return self.turn_on(**kwargs)

    async def async_toggle(self, **kwargs: Dict) -> Optional[Awaitable[Any]]:
        """Toggle the entity.

        This method must be run in the event loop and returns a coroutine.
        """
        if self.is_on:
            return await self.async_turn_off(**kwargs)
        return await self.async_turn_on(**kwargs)
