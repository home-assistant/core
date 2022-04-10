"""Support for Android IP Webcam settings."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_HOST,
    CONF_NAME,
    CONF_SWITCHES,
    DATA_IP_WEBCAM,
    ICON_MAP,
    KEY_MAP,
    AndroidIPCamEntity,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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
        self._attr_name = f"{name} {self._mapped_name}"
        self._attr_is_on = False

    async def async_update(self):
        """Get the updated status of the switch."""
        self._attr_is_on = bool(self._ipcam.current_settings.get(self._setting))

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
        self._attr_is_on = True
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
        self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def icon(self):
        """Return the icon for the switch."""
        return ICON_MAP.get(self._setting, "mdi:flash")
