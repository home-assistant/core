"""
Support for Freebox devices (Freebox v6 and Freebox mini 4K).

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.freebox/
"""
import logging

from homeassistant.components.freebox import DATA_FREEBOX
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['freebox']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the sensors."""
    fbx = hass.data[DATA_FREEBOX]
    perms_settings = discovery_info.get('perms_settings')
    async_add_entities([
        FbxWifiSwitch(fbx, perms_settings)
    ], True)


class FbxSwitch(SwitchDevice):
    """Representation of a Freebox switch."""

    _name = 'generic'

    def __init__(self, fbx):
        """Initilize the switch."""
        self.state = None
        self.fbx = fbx

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_get_perms(self):
        """Get permissions from Freebox."""
        self._permissions = await self.fbx.get_permissions()


class FbxWifiSwitch(FbxSwitch):
    """Representation of a freebox wifi switch."""

    def __init__(self, fbx, perms_settings):
        """Initilize the Wifi switch."""
        self._name = 'Freebox WiFi'
        self._state = None
        self.perms_settings = perms_settings
        self.fbx = fbx

    @property
    def available(self):
        """If permission is not true the switch is not available."""
        if not self.perms_settings:
            return False
        return True

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        from aiofreepybox.exceptions import InsufficientPermissionsError

        wifi_config = {"enabled": True}
        try:
            await self.fbx.wifi.set_global_config(wifi_config)
        except InsufficientPermissionsError:
            _LOGGER.warning('Home Assistant does not have permissions to'
                            ' modify the settings. Please refer to'
                            ' documentation. https://home-assistant.io/'
                            'components/switch.freebox/')

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        from aiofreepybox.exceptions import InsufficientPermissionsError

        wifi_config = {"enabled": False}
        try:
            await self.fbx.wifi.set_global_config(wifi_config)
        except InsufficientPermissionsError:
            _LOGGER.warning('Home Assistant does not have permissions to'
                            ' modify the settings. Please refer to'
                            ' documentation. https://home-assistant.io/'
                            'components/switch.freebox/')

    async def async_update(self):
        """Get the state and update it."""
        from aiofreepybox.constants import PERMISSION_SETTINGS

        await super().async_get_perms()
        self.perms_settings = True if self._permissions.get(
                                      PERMISSION_SETTINGS) else False
        datas = await self.fbx.wifi.get_global_config()
        active = datas['enabled']
        self._state = True if active else False
