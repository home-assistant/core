"""Support for System Bridge updates."""

from homeassistant.components.update import UpdateEntity
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge update based on a config entry."""
    coordinator = entry.runtime_data

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
    _attr_name = None

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
