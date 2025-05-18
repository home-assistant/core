"""Support for System Bridge updates."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge update based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            SystemBridgeUpdateEntity(
                coordinator,
                entry.data[CONF_PORT],
            ),
        ]
    )


class SystemBridgeUpdateEntity(SystemBridgeEntity, UpdateEntity):
    """Defines a System Bridge update entity."""

    _attr_has_entity_name = True
    _attr_title = "System Bridge"

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api_port,
            "update",
        )
        self._attr_name = coordinator.data.system.hostname

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self.coordinator.data.system.version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.coordinator.data.system.version_latest

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return f"https://github.com/timmo001/system-bridge/releases/tag/{self.coordinator.data.system.version_latest}"
