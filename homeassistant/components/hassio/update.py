"""Update platform for Supervisor."""

from __future__ import annotations

import re
from typing import Any

from aiohasupervisor import SupervisorError
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ADDONS_COORDINATOR,
    ATTR_AUTO_UPDATE,
    ATTR_VERSION,
    ATTR_VERSION_LATEST,
    DATA_KEY_ADDONS,
    DATA_KEY_CORE,
    DATA_KEY_OS,
    DATA_KEY_SUPERVISOR,
)
from .entity import (
    HassioAddonEntity,
    HassioCoreEntity,
    HassioOSEntity,
    HassioSupervisorEntity,
)
from .update_helper import update_addon, update_core, update_os

ENTITY_DESCRIPTION = UpdateEntityDescription(
    translation_key="update",
    key=ATTR_VERSION_LATEST,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Supervisor update based on a config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities = [
        SupervisorSupervisorUpdateEntity(
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        ),
        SupervisorCoreUpdateEntity(
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        ),
    ]

    entities.extend(
        SupervisorAddonUpdateEntity(
            addon=addon,
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        )
        for addon in coordinator.data[DATA_KEY_ADDONS].values()
    )

    if coordinator.is_hass_os:
        entities.append(
            SupervisorOSUpdateEntity(
                coordinator=coordinator,
                entity_description=ENTITY_DESCRIPTION,
            )
        )

    async_add_entities(entities)


class SupervisorAddonUpdateEntity(HassioAddonEntity, UpdateEntity):
    """Update entity to handle updates for the Supervisor add-ons."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.BACKUP
        | UpdateEntityFeature.RELEASE_NOTES
    )

    @property
    def _addon_data(self) -> dict:
        """Return the add-on data."""
        return self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug]

    @property
    def auto_update(self) -> bool:
        """Return true if auto-update is enabled for the add-on."""
        return self._addon_data[ATTR_AUTO_UPDATE]

    @property
    def title(self) -> str | None:
        """Return the title of the update."""
        return self._addon_data[ATTR_NAME]

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._addon_data[ATTR_VERSION_LATEST]

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._addon_data[ATTR_VERSION]

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the add-on if any."""
        if not self.available:
            return None
        if self._addon_data[ATTR_ICON]:
            return f"/api/hassio/addons/{self._addon_slug}/icon"
        return None

    async def async_release_notes(self) -> str | None:
        """Return the release notes for the update."""
        if (
            changelog := await self.coordinator.get_changelog(self._addon_slug)
        ) is None:
            return None

        if self.latest_version is None or self.installed_version is None:
            return changelog

        regex_pattern = re.compile(
            rf"^#* {re.escape(self.latest_version)}\n(?:^(?!#* {re.escape(self.installed_version)}).*\n)*",
            re.MULTILINE,
        )
        match = regex_pattern.search(changelog)
        return match.group(0) if match else changelog

    async def async_install(
        self,
        version: str | None = None,
        backup: bool = False,
        **kwargs: Any,
    ) -> None:
        """Install an update."""
        await update_addon(
            self.hass, self._addon_slug, backup, self.title, self.installed_version
        )
        await self.coordinator.async_refresh()


class SupervisorOSUpdateEntity(HassioOSEntity, UpdateEntity):
    """Update entity to handle updates for the Home Assistant Operating System."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.BACKUP
    )
    _attr_title = "Home Assistant Operating System"

    @property
    def latest_version(self) -> str:
        """Return the latest version."""
        return self.coordinator.data[DATA_KEY_OS][ATTR_VERSION_LATEST]

    @property
    def installed_version(self) -> str:
        """Return the installed version."""
        return self.coordinator.data[DATA_KEY_OS][ATTR_VERSION]

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the entity."""
        return "https://brands.home-assistant.io/homeassistant/icon.png"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        version = AwesomeVersion(self.latest_version)
        if version.dev or version.strategy == AwesomeVersionStrategy.UNKNOWN:
            return "https://github.com/home-assistant/operating-system/commits/dev"
        return (
            f"https://github.com/home-assistant/operating-system/releases/tag/{version}"
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await update_os(self.hass, version, backup)


class SupervisorSupervisorUpdateEntity(HassioSupervisorEntity, UpdateEntity):
    """Update entity to handle updates for the Home Assistant Supervisor."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_title = "Home Assistant Supervisor"

    @property
    def latest_version(self) -> str:
        """Return the latest version."""
        return self.coordinator.data[DATA_KEY_SUPERVISOR][ATTR_VERSION_LATEST]

    @property
    def installed_version(self) -> str:
        """Return the installed version."""
        return self.coordinator.data[DATA_KEY_SUPERVISOR][ATTR_VERSION]

    @property
    def auto_update(self) -> bool:
        """Return true if auto-update is enabled for supervisor."""
        return self.coordinator.data[DATA_KEY_SUPERVISOR][ATTR_AUTO_UPDATE]

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        version = AwesomeVersion(self.latest_version)
        if version.dev or version.strategy == AwesomeVersionStrategy.UNKNOWN:
            return "https://github.com/home-assistant/supervisor/commits/main"
        return f"https://github.com/home-assistant/supervisor/releases/tag/{version}"

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the entity."""
        return "https://brands.home-assistant.io/hassio/icon.png"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        try:
            await self.coordinator.supervisor_client.supervisor.update()
        except SupervisorError as err:
            raise HomeAssistantError(
                f"Error updating Home Assistant Supervisor: {err}"
            ) from err


class SupervisorCoreUpdateEntity(HassioCoreEntity, UpdateEntity):
    """Update entity to handle updates for Home Assistant Core."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.BACKUP
    )
    _attr_title = "Home Assistant Core"

    @property
    def latest_version(self) -> str:
        """Return the latest version."""
        return self.coordinator.data[DATA_KEY_CORE][ATTR_VERSION_LATEST]

    @property
    def installed_version(self) -> str:
        """Return the installed version."""
        return self.coordinator.data[DATA_KEY_CORE][ATTR_VERSION]

    @property
    def entity_picture(self) -> str | None:
        """Return the icon of the entity."""
        return "https://brands.home-assistant.io/homeassistant/icon.png"

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        version = AwesomeVersion(self.latest_version)
        if version.dev:
            return "https://github.com/home-assistant/core/commits/dev"
        return f"https://{'rc' if version.beta else 'www'}.home-assistant.io/latest-release-notes/"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await update_core(self.hass, version, backup)
