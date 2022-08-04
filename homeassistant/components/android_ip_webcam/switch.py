"""Support for Android IP Webcam settings."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AndroidIPCamBaseEntity, AndroidIPCamDataUpdateCoordinator
from .const import DOMAIN, SWITCH_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IP Webcam switches from config entry."""

    coordinator: AndroidIPCamDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    switch_types = [
        switch
        for switch in SWITCH_TYPES
        if switch.key in coordinator.ipcam.enabled_settings
    ]
    async_add_entities(
        [
            IPWebcamSettingSwitch(coordinator, description)
            for description in switch_types
        ]
    )


class IPWebcamSettingSwitch(AndroidIPCamBaseEntity, SwitchEntity):
    """Representation of a IP Webcam setting."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AndroidIPCamDataUpdateCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return if settings is on or off."""
        return bool(self._ipcam.current_settings.get(self.entity_description.key))

    async def async_turn_on(self, **kwargs):
        """Turn device on."""
        if self.entity_description.key == "torch":
            await self._ipcam.torch(activate=True)
        elif self.entity_description.key == "focus":
            await self._ipcam.focus(activate=True)
        elif self.entity_description.key == "video_recording":
            await self._ipcam.record(record=True)
        else:
            await self._ipcam.change_setting(self.entity_description.key, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn device off."""
        if self.entity_description.key == "torch":
            await self._ipcam.torch(activate=False)
        elif self.entity_description.key == "focus":
            await self._ipcam.focus(activate=False)
        elif self.entity_description.key == "video_recording":
            await self._ipcam.record(record=False)
        else:
            await self._ipcam.change_setting(self.entity_description.key, False)
        await self.coordinator.async_request_refresh()
