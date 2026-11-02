"""Firmware updates for Victron GX devices."""

from typing import Any, override

from victron_mqtt import FirmwareUpdateError, FirmwareUpdateInfo

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .hub import VictronGxConfigEntry

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.

_FIRMWARE_UPDATE_URL = "https://professional.victronenergy.com/news/"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GX firmware update entity."""
    async_add_entities([VictronFirmwareUpdateEntity(config_entry)], True)


class VictronFirmwareUpdateEntity(UpdateEntity):
    """Represent the Venus OS firmware installed on a GX device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_release_url = _FIRMWARE_UPDATE_URL
    _attr_should_poll = False
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_title = "Venus OS"

    def __init__(self, entry: VictronGxConfigEntry) -> None:
        """Initialize the firmware update entity."""
        self._hub = entry.runtime_data
        self._firmware_info = self._hub.firmware_update_info
        self._installing = False
        self._attr_unique_id = f"{entry.unique_id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}_system_0")}
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register for firmware update information changes."""
        await super().async_added_to_hass()
        self._hub.register_firmware_update_callback(self._on_firmware_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister the firmware update callback."""
        self._hub.unregister_firmware_update_callback()
        await super().async_will_remove_from_hass()

    @callback
    def _on_firmware_update(self, info: FirmwareUpdateInfo) -> None:
        """Handle updated firmware information."""
        self._firmware_info = info
        self._attr_in_progress = self._installing or info.in_progress
        if not self._attr_in_progress:
            self._attr_update_percentage = None
        elif info.in_progress and info.progress is not None:
            self._attr_update_percentage = info.progress
        self.async_write_ha_state()

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed Venus OS version."""
        return (
            self._firmware_info.installed_version
            if self._firmware_info is not None
            else None
        )

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest available Venus OS version."""
        if self._firmware_info is None:
            return None
        return (
            self._firmware_info.available_version
            or self._firmware_info.installed_version
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the installed firmware version is available."""
        return super().available and self.installed_version is not None

    @property
    @override
    def has_update(self) -> bool:
        """Return whether Victron offers a Venus OS firmware build."""
        return self._firmware_info is not None and self._firmware_info.update_available

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest Venus OS firmware."""
        if not self.has_update:
            return

        self._installing = self._attr_in_progress = True
        self.async_write_ha_state()

        @callback
        def _async_update_progress(progress: int) -> None:
            self._attr_update_percentage = progress
            self.async_write_ha_state()

        try:
            await self._hub.install_firmware_update(_async_update_progress)
        except FirmwareUpdateError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=err.reason.value,
            ) from err
        finally:
            self._installing = False
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()
