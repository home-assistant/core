"""Support for Freebox Delta, Revolution and Mini 4K."""
import logging
from typing import Dict

from aiofreepybox.exceptions import InsufficientPermissionsError

from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the platform."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the switch."""
    fbx = hass.data[DOMAIN]
    async_add_entities([FbxWifiSwitch(fbx)], True)


class FbxWifiSwitch(SwitchDevice):
    """Representation of a freebox wifi switch."""

    def __init__(self, fbx: FreeboxRouter):
        """Initialize the Wifi switch."""
        self._name = "Freebox WiFi"
        self._state = None
        self._fbx = fbx
        self._unique_id = f"{self._fbx.mac} {self._name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return self._fbx.device_info

    async def _async_set_state(self, enabled: bool):
        """Turn the switch on or off."""
        wifi_config = {"enabled": enabled}
        try:
            await self._fbx.wifi.set_global_config(wifi_config)
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation."
            )

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._async_set_state(False)

    async def async_update(self):
        """Get the state and update it."""
        datas = await self._fbx.wifi.get_global_config()
        active = datas["enabled"]
        self._state = bool(active)
