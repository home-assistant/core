"""Home Assistant Switcher Component Switch platform."""

from datetime import datetime
from logging import getLogger
from typing import Callable, cast, Dict, Optional

from homeassistant.components.switch import ATTR_CURRENT_POWER_W, SwitchDevice
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.core import HomeAssistant, Event
from homeassistant.exceptions import PlatformNotReady

from . import (
    ATTR_AUTO_OFF_SET, ATTR_DEVICE_NAME, ATTR_ELECTRIC_CURRNET,
    ATTR_IP_ADDRESS, ATTR_LAST_DATA_UPDATE, ATTR_LAST_STATE_CHANGE,
    ATTR_REMAINING_TIME, DATA_CONFIG, DATA_DEVICE, DOMAIN,
    EVENT_SWITCHER_DEVICE_UPDATED, UPDATED_DEVICE)

_LOGGER = getLogger(__name__)

DEPENDENCIES = ['switcher_kis']

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
    if hass.data[DOMAIN][DISCOVERY_CONFIG]:
        name = hass.data[DOMAIN][DISCOVERY_CONFIG][CONF_NAME].title()
        icon = hass.data[DOMAIN][DISCOVERY_CONFIG].get(CONF_ICON)
    else:
        raise PlatformNotReady("No config data found")

    if hass.data[DOMAIN].get(DISCOVERY_DEVICE):
        switcher_entity = SwitcherControl(
            hass, name, icon, hass.data[DOMAIN].get(DISCOVERY_DEVICE))
    else:
        raise PlatformNotReady("No device data discoverd")

    async_add_entities([switcher_entity])


class SwitcherControl(SwitchDevice):
    """Home Assistant switch entity."""

    from aioswitcher.devices import SwitcherV2Device

    def __init__(self, hass: HomeAssistant, name: str, icon: Optional[str],
                 device_data: SwitcherV2Device) -> None:
        """Initialize the entity."""
        self._hass = hass
        self._name = name
        self._icon = icon
        self._self_initiated = False

        self._device_data = device_data
        self._state = device_data.state
        hass.bus.async_listen(EVENT_SWITCHER_DEVICE_UPDATED,
                              self.async_update_data)

    @property
    def device_ip_addr(self) -> str:
        """Return the device's ip address."""
        return cast(str, self._device_data.ip_addr)

    @property
    def electric_current(self) -> float:
        """Return the electric current."""
        return cast(float, self._device_data.electric_current)

    @property
    def remaining_time(self) -> Optional[str]:
        """Return the remaining time to off command."""
        return self._device_data.remaining_time \
            if isinstance(self._device_data.remaining_time, str) \
            else None

    @property
    def auto_off_set(self) -> str:
        """Return the auto off configuration set."""
        return cast(str, self._device_data.auto_off_set)

    @property
    def last_data_update(self) -> datetime:
        """Return the datetime for the last update received by the device."""
        return cast(datetime, self._device_data.last_data_update)

    @property
    def last_state_change(self) -> datetime:
        """Return the datetime for the last state change."""
        return cast(datetime, self._device_data.last_state_change)

    @property
    def device_name(self) -> str:
        """Return the device's name."""
        return cast(str, self._device_data.name)

    @property
    def should_poll(self) -> bool:
        """Return False, entity pushes its state to HA."""
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
    def is_on(self) -> bool:
        """Return True if entity is on."""
        from aioswitcher.consts import STATE_ON as SWITCHER_STATE_ON
        return cast(bool, self._state == SWITCHER_STATE_ON)

    @property
    def current_power_w(self) -> int:
        """Return the current power usage in W."""
        return cast(int, self._device_data.power_consumption)

    @property
    def device_state_attributes(self) -> Dict:
        """Return the optional state attributes."""
        from aioswitcher.consts import WAITING_TEXT

        attribs = {}

        for prop, attr in PROPERTIES_TO_ATTRIBUTES.items():
            value = getattr(self, prop)
            if value and value is not WAITING_TEXT:
                attribs[attr] = value

        return attribs

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        from aioswitcher.consts import (STATE_OFF as SWITCHER_STATE_OFF,
                                        STATE_ON as SWITCHER_STATE_ON)
        return self._state in [SWITCHER_STATE_ON, SWITCHER_STATE_OFF]

    async def async_update_data(self, event: Event) -> None:
        """Update the entity data."""
        device_data = event.data.get(UPDATED_DEVICE)
        if device_data:
            if self._self_initiated:
                self._self_initiated = False
            else:
                self._device_data = device_data
                self._state = self._device_data.state
                self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Dict) -> None:
        """Turn the entity on.

        This method must be run in the event loop and returns a coroutine.
        """
        from aioswitcher.api import SwitcherV2Api
        # pylint: disable=unused-import
        from aioswitcher.api.messages import (  # noqa F401
            SwitcherV2ControlResponseMSG)
        # pylint: enable=unused-import
        from aioswitcher.consts import (COMMAND_ON,
                                        STATE_ON as SWITCHER_STATE_ON)
        response = None  # type: SwitcherV2ControlResponseMSG
        async with SwitcherV2Api(
                self._hass.loop, self.device_ip_addr,
                self._device_data.phone_id, self._device_data.device_id,
                self._device_data.device_password) as swapi:
            response = await swapi.control_device(COMMAND_ON)

        if response and response.successful:
            self._self_initiated = True
            self._state = SWITCHER_STATE_ON
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Dict) -> None:
        """Turn the entity off.

        This method must be run in the event loop and returns a coroutine.
        """
        from aioswitcher.api import SwitcherV2Api
        # pylint: disable=unused-import
        from aioswitcher.api.messages import (  # noqa F401
            SwitcherV2ControlResponseMSG)
        # pylint: enable=unused-import
        from aioswitcher.consts import (COMMAND_OFF,
                                        STATE_OFF as SWITCHER_STATE_OFF)
        response = None  # type: SwitcherV2ControlResponseMSG
        async with SwitcherV2Api(
                self._hass.loop, self.device_ip_addr,
                self._device_data.phone_id, self._device_data.device_id,
                self._device_data.device_password) as swapi:
            response = await swapi.control_device(COMMAND_OFF)

        if response and response.successful:
            self._self_initiated = True
            self._state = SWITCHER_STATE_OFF
            self.async_schedule_update_ha_state()
