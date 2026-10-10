"""AdGuard Home Update platform."""

from typing import Any, override

from adguardhome import AdGuardHomeError

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import AdGuardConfigEntry, AdGuardHomeUpdateCoordinator
from .entity import AdGuardHomeEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AdGuard Home update entity based on a config entry."""
    coordinator = entry.runtime_data.update

    # AdGuard Home can be built or started without its updater. When the first
    # check failed, assume it has one, rather than hide it for good.
    if coordinator.data is not None and coordinator.data.disabled:
        return

    async_add_entities([AdGuardHomeUpdate(coordinator)])


class AdGuardHomeUpdate(AdGuardHomeEntity[AdGuardHomeUpdateCoordinator], UpdateEntity):
    """Defines an AdGuard Home update."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_name = None

    def __init__(self, coordinator: AdGuardHomeUpdateCoordinator) -> None:
        """Initialize AdGuard Home update."""
        super().__init__(coordinator)
        entry = coordinator.config_entry

        # Legacy format, kept as migrating existing unique IDs is not worth the risk
        self._attr_unique_id = "_".join(  # pylint: disable=home-assistant-entity-unique-id-redundant-domain,home-assistant-entity-unique-id-redundant-platform
            [DOMAIN, entry.data[CONF_HOST], str(entry.data[CONF_PORT]), "update"]
        )

    @property
    @override
    def installed_version(self) -> str:
        """Return the version AdGuard Home runs."""
        state = self.coordinator.config_entry.runtime_data.state
        return str(state.data.status.version)

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the latest version of AdGuard Home."""
        if (new_version := self.coordinator.data.new_version) is None:
            return None
        return str(new_version)

    @property
    @override
    def release_summary(self) -> str | None:
        """Return the announcement of the latest version."""
        return self.coordinator.data.announcement

    @property
    @override
    def release_url(self) -> str | None:
        """Return the URL of the announcement of the latest version."""
        return self.coordinator.data.announcement_url

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install latest update."""
        try:
            await self.coordinator.client.update.install()
        except AdGuardHomeError as err:
            raise HomeAssistantError(f"Failed to install update: {err}") from err
        self.hass.config_entries.async_schedule_reload(
            self.coordinator.config_entry.entry_id
        )
