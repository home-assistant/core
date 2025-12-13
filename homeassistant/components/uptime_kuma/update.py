"""Update platform for the Uptime Kuma integration."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UPTIME_KUMA_KEY
from .const import DOMAIN
from .coordinator import (
    UptimeKumaConfigEntry,
    UptimeKumaDataUpdateCoordinator,
    UptimeKumaSoftwareUpdateCoordinator,
)

PARALLEL_UPDATES = 0


class UptimeKumaUpdate(StrEnum):
    """Uptime Kuma update."""

    UPDATE = "update"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UptimeKumaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up update platform."""

    coordinator = entry.runtime_data
    async_add_entities(
        [UptimeKumaUpdateEntity(coordinator, hass.data[UPTIME_KUMA_KEY])]
    )


class UptimeKumaUpdateEntity(
    CoordinatorEntity[UptimeKumaDataUpdateCoordinator], UpdateEntity
):
    """Representation of an update entity."""

    entity_description = UpdateEntityDescription(
        key=UptimeKumaUpdate.UPDATE,
        translation_key=UptimeKumaUpdate.UPDATE,
    )
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UptimeKumaDataUpdateCoordinator,
        update_coordinator: UptimeKumaSoftwareUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.update_checker = update_coordinator

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=coordinator.config_entry.title,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Uptime Kuma",
            configuration_url=coordinator.config_entry.data[CONF_URL],
            sw_version=coordinator.api.version.version,
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{self.entity_description.key}"
        )

    @property
    def installed_version(self) -> str | None:
        """Current version."""

        return self.coordinator.api.version.version

    @property
    def title(self) -> str | None:
        """Title of the release."""

        return f"Uptime Kuma {self.update_checker.data.name}"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes."""

        return self.update_checker.data.html_url

    @property
    def latest_version(self) -> str | None:
        """Latest version."""

        return self.update_checker.data.tag_name

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        return self.update_checker.data.body

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass.

        Register extra update listener for the software update coordinator.
        """
        await super().async_added_to_hass()
        self.async_on_remove(
            self.update_checker.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.update_checker.last_update_success
