"""Support for Android IP Webcam settings."""
from homeassistant.components.switch import SwitchEntity

from . import (
    CONF_HOST,
    CONF_NAME,
    CONF_SWITCHES,
    DATA_IP_WEBCAM,
    ICON_MAP,
    KEY_MAP,
    AndroidIPCamEntity,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the IP Webcam switch platform."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    name = discovery_info[CONF_NAME]
    switches = discovery_info[CONF_SWITCHES]
    ipcam = hass.data[DATA_IP_WEBCAM][host]

    all_switches = []

    for setting in switches:
        all_switches.append(IPWebcamSettingsSwitch(name, host, ipcam, setting))

    async_add_entities(all_switches, True)


class IPWebcamSettingsSwitch(AndroidIPCamEntity, SwitchEntity):
    """An abstract class for an IP Webcam setting."""

    def __init__(self, name, host, ipcam, setting):
        """Initialize the settings switch."""
        super().__init__(host, ipcam)

        self._setting = setting
        self._mapped_name = KEY_MAP.get(self._setting, self._setting)
        self._name = f"{name} {self._mapped_name}"
        self._state = False

    @property
    def name(self):
        """Return the name of the node."""
        return self._name

    async def async_update(self):
        """Get the updated status of the switch."""
        self._state = bool(self._ipcam.current_settings.get(self._setting))

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn device on."""
        if self._setting == "torch":
            await self._ipcam.torch(activate=True)
        elif self._setting == "focus":
            await self._ipcam.focus(activate=True)
        elif self._setting == "video_recording":
            await self._ipcam.record(record=True)
        else:
            await self._ipcam.change_setting(self._setting, True)
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn device off."""
        if self._setting == "torch":
            await self._ipcam.torch(activate=False)
        elif self._setting == "focus":
            await self._ipcam.focus(activate=False)
        elif self._setting == "video_recording":
            await self._ipcam.record(record=False)
        else:
            await self._ipcam.change_setting(self._setting, False)
        self._state = False
        self.async_write_ha_state()

    @property
    def icon(self):
        """Return the icon for the switch."""
        return ICON_MAP.get(self._setting, "mdi:flash")
