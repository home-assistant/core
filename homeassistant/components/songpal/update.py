"""Update platform for Songpal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.components.update.const import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SongpalCoordinator
from .entity import SongpalEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up songpal media player."""
    coordinator: SongpalCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [SognpalUpdateEntity(coordinator)]

    async_add_entities(entities)


class SognpalUpdateEntity(UpdateEntity, SongpalEntity):
    """Software update availability sensor."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL

    _attr_base_name = "Firmware Update"

    @property
    def unique_id(self) -> str:
        """Create a unique identifier for the entity."""
        return f"{self.coordinator.data.unique_id}-update"

    @property
    def auto_update(self) -> bool:
        """Return whether the device is set to auto-update."""
        return self.coordinator.data.settings["system-autoupdate"].currentValue == "on"

    @property
    def installed_version(self) -> str:
        """Return the current version of the firmware."""
        return self.coordinator.data.system_information.version

    @property
    def latest_version(self) -> str | None:
        """Return the current available version of the firmware, if any."""
        if self.coordinator.data.sw_update_info.isUpdatable:
            return self.coordinator.data.sw_update_info.swInfo.updatableVersion

        return None

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update.

        No specific version can be provided, and no backup can be taken.
        """

        assert version is None and not backup

        await self.coordinator.device.activate_system_update()
