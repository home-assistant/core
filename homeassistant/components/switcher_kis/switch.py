"""Home Assistant Switcher Component Switch platform."""

from logging import getLogger
from typing import TYPE_CHECKING, Callable, Dict

from aioswitcher.api import SwitcherV2Api
from aioswitcher.consts import (
    COMMAND_OFF,
    COMMAND_ON,
    STATE_OFF as SWITCHER_STATE_OFF,
    STATE_ON as SWITCHER_STATE_ON,
    WAITING_TEXT,
)

from homeassistant.components.switch import ATTR_CURRENT_POWER_W, SwitchEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    ATTR_AUTO_OFF_SET,
    ATTR_ELECTRIC_CURRENT,
    ATTR_REMAINING_TIME,
    DATA_DEVICE,
    DOMAIN,
    SIGNAL_SWITCHER_DEVICE_UPDATE,
)

# pylint: disable=ungrouped-imports
if TYPE_CHECKING:
    from aioswitcher.devices import SwitcherV2Device
    from aioswitcher.api.messages import SwitcherV2ControlResponseMSG


_LOGGER = getLogger(__name__)

DEVICE_PROPERTIES_TO_HA_ATTRIBUTES = {
    "power_consumption": ATTR_CURRENT_POWER_W,
    "electric_current": ATTR_ELECTRIC_CURRENT,
    "remaining_time": ATTR_REMAINING_TIME,
    "auto_off_set": ATTR_AUTO_OFF_SET,
}


async def async_setup_platform(
    hass: HomeAssistantType,
    config: Dict,
    async_add_entities: Callable,
    discovery_info: Dict,
) -> None:
    """Set up the switcher platform for the switch component."""
    if discovery_info is None:
        return
    async_add_entities([SwitcherControl(hass.data[DOMAIN][DATA_DEVICE])])


class SwitcherControl(SwitchEntity):
    """Home Assistant switch entity."""

    def __init__(self, device_data: "SwitcherV2Device") -> None:
        """Initialize the entity."""
        self._self_initiated = False
        self._device_data = device_data
        self._state = device_data.state

    @property
    def name(self) -> str:
        """Return the device's name."""
        return self._device_data.name

    @property
    def should_poll(self) -> bool:
        """Return False, entity pushes its state to HA."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device_data.device_id}-{self._device_data.mac_addr}"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""

        return self._state == SWITCHER_STATE_ON

    @property
    def current_power_w(self) -> int:
        """Return the current power usage in W."""
        return self._device_data.power_consumption

    @property
    def device_state_attributes(self) -> Dict:
        """Return the optional state attributes."""

        attribs = {}

        for prop, attr in DEVICE_PROPERTIES_TO_HA_ATTRIBUTES.items():
            value = getattr(self._device_data, prop)
            if value and value is not WAITING_TEXT:
                attribs[attr] = value

        return attribs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        return self._state in [SWITCHER_STATE_ON, SWITCHER_STATE_OFF]

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SWITCHER_DEVICE_UPDATE, self.async_update_data
            )
        )

    async def async_update_data(self, device_data: "SwitcherV2Device") -> None:
        """Update the entity data."""
        if device_data:
            if self._self_initiated:
                self._self_initiated = False
            else:
                self._device_data = device_data
                self._state = self._device_data.state
                self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Dict) -> None:
        """Turn the entity on."""
        await self._control_device(True)

    async def async_turn_off(self, **kwargs: Dict) -> None:
        """Turn the entity off."""
        await self._control_device(False)

    async def _control_device(self, send_on: bool) -> None:
        """Turn the entity on or off."""

        response: "SwitcherV2ControlResponseMSG" = None
        async with SwitcherV2Api(
            self.hass.loop,
            self._device_data.ip_addr,
            self._device_data.phone_id,
            self._device_data.device_id,
            self._device_data.device_password,
        ) as swapi:
            response = await swapi.control_device(
                COMMAND_ON if send_on else COMMAND_OFF
            )

        if response and response.successful:
            self._self_initiated = True
            self._state = SWITCHER_STATE_ON if send_on else SWITCHER_STATE_OFF
            self.async_write_ha_state()
