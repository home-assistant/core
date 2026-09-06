"""Update platform for the WattWächter Plus integration."""

from typing import Any, override

from aio_wattwaechter import WattwaechterError

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import WattwaechterConfigEntry, WattwaechterCoordinator
from .entity import WattwaechterEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattwaechterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WattWächter firmware update entity."""
    async_add_entities([WattwaechterUpdateEntity(entry.runtime_data)])


class WattwaechterUpdateEntity(WattwaechterEntity, UpdateEntity):
    """Firmware update entity for WattWächter Plus."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(self, coordinator: WattwaechterCoordinator) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device_id

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        system = self.coordinator.data.system
        if system is not None and (version := system.get_value("esp", "os_version")):
            return version
        return self.coordinator.fw_version

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        ota = self.coordinator.data.ota
        if ota is None:
            return None
        if ota.update_available:
            return ota.version
        return self.installed_version

    @override
    def release_notes(self) -> str | None:
        """Return the release notes for the available firmware."""
        ota = self.coordinator.data.ota
        if ota is None:
            return None
        return ota.release_note_en or None

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the available firmware update."""
        try:
            success = await self.coordinator.client.ota_start()
        except WattwaechterError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="ota_failed"
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="ota_failed"
            )
