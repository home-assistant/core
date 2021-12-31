"""Base entity for Songpal-enabled (Sony) media devices."""
from __future__ import annotations

import logging

from songpal.containers import SettingCandidate, SettingsEntry

from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SongpalCoordinator

_LOGGER = logging.getLogger(__name__)

_SETTINGS_ICONS = {
    "sound-night": "mdi:power-sleep",
    "sound-voice": "mdi:account-voice",
}


class SongpalEntity(CoordinatorEntity[SongpalCoordinator]):
    """Base class for Songpal entities."""

    coordinator: SongpalCoordinator

    _attr_base_name: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for the current Songpal device."""
        return self.coordinator.data.device_info

    @property
    def name(self) -> str:
        """Construct a default name, if given a base name."""
        if self._attr_base_name:
            return f"{self.coordinator.name} {self._attr_base_name}"

        return f"{self.coordinator.name}"


class SongpalSettingEntity(SongpalEntity):
    """A Songpal entity that relates directly to a (sound) setting."""

    def __init__(self, coordinator: SongpalCoordinator, setting: SettingsEntry) -> None:
        """Instantiate a new Songpal entity attached to a setting."""
        super().__init__(coordinator)

        self._setting = setting

        _LOGGER.debug("Creating a new setting entity for %s", self._setting.titleTextID)

        self._attr_base_name = self._setting.title
        self._attr_unique_id = (
            f"{self.coordinator.data.unique_id}-{self._setting.titleTextID}"
        )
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = _SETTINGS_ICONS.get(self._setting.titleTextID, None)

    @property
    def candidates(self) -> list[SettingCandidate]:
        """Return the list of candidates for the settings."""
        if self._setting.titleTextID not in self.coordinator.data.settings:
            return []

        return self.coordinator.data.settings[self._setting.titleTextID].candidate

    @property
    def _current_value(self) -> str | None:
        return self.coordinator.data.settings[self._setting.titleTextID].currentValue

    @property
    def available(self) -> bool:
        """Return whether the setting is available to change."""
        return (
            super().available
            and self._setting.titleTextID in self.coordinator.data.settings
            and self.coordinator.data.settings[self._setting.titleTextID].isAvailable
        )

    async def update_setting(self, value_or_candidate: str | SettingCandidate) -> None:
        """Update the value of the attached setting."""
        if isinstance(value_or_candidate, SettingCandidate):
            value = value_or_candidate.value
        else:
            value = value_or_candidate

        _LOGGER.debug(
            "[%s] Setting '%s' to '%s'", self.name, self._setting.titleTextID, value
        )

        await self.coordinator.device.services[self._setting.apiMapping.service][
            self._setting.apiMapping.setApi["name"]
        ]({"settings": [{"target": self._setting.apiMapping.target, "value": value}]})
