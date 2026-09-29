"""Firmware update information for OPNsense routers."""

from typing import cast, override

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.const import CONF_URL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OPNsenseFirmwareCoordinator
from .types import OPNsenseConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OPNsenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the router firmware update entity."""
    coordinator = OPNsenseFirmwareCoordinator(hass, entry, entry.runtime_data.client)
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([OPNsenseFirmwareUpdate(coordinator, entry)])


class OPNsenseFirmwareUpdate(
    CoordinatorEntity[OPNsenseFirmwareCoordinator], UpdateEntity
):
    """Represent the router firmware update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "firmware"

    def __init__(
        self, coordinator: OPNsenseFirmwareCoordinator, entry: OPNsenseConfigEntry
    ) -> None:
        """Initialize the firmware entity."""
        super().__init__(coordinator)
        assert entry.unique_id is not None
        self._attr_unique_id = f"{entry.unique_id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title or "OPNsense",
            manufacturer="OPNsense",
            configuration_url=entry.data[CONF_URL],
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether firmware versions are available."""
        return (
            super().available
            and bool(self.installed_version)
            and bool(self.latest_version)
        )

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        return cast(
            str | None, self.coordinator.data.get("product", {}).get("product_version")
        )

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        if self.coordinator.data.get("status") == "upgrade" and (
            major_version := self.coordinator.data.get("upgrade_major_version")
        ):
            return cast(str, major_version)

        product = self.coordinator.data.get("product", {})
        latest_version = product.get("product_latest")
        if (
            self.coordinator.data.get("status") == "update"
            and latest_version == product.get("product_version")
            and latest_version
        ):
            return f"{latest_version} (package updates available)"
        return cast(str | None, latest_version)
