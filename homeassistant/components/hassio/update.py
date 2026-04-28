"""Update platform for Supervisor."""

from __future__ import annotations

import re
from typing import Any

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Job
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
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
    MAIN_COORDINATOR,
)
from .entity import (
    HassioAddonEntity,
    HassioCoreEntity,
    HassioOSEntity,
    HassioSupervisorEntity,
)
from .jobs import JobSubscription
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
    coordinator = hass.data[MAIN_COORDINATOR]

    entities: list[UpdateEntity] = [
        SupervisorSupervisorUpdateEntity(
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        ),
        SupervisorCoreUpdateEntity(
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        ),
    ]

    if coordinator.is_hass_os:
        entities.append(
            SupervisorOSUpdateEntity(
                coordinator=coordinator,
                entity_description=ENTITY_DESCRIPTION,
            )
        )

    addons_coordinator = hass.data[ADDONS_COORDINATOR]
    entities.extend(
        SupervisorAddonUpdateEntity(
            addon=addon,
            coordinator=addons_coordinator,
            entity_description=ENTITY_DESCRIPTION,
        )
        for addon in addons_coordinator.data[DATA_KEY_ADDONS].values()
    )

    async_add_entities(entities)


class SupervisorAddonUpdateEntity(HassioAddonEntity, UpdateEntity):
    """Update entity to handle updates for the Supervisor add-ons.

    The ``addon_manager_update`` job emits a ``done=True`` WS event as soon as
    Supervisor finishes the container work, a few milliseconds before the
    ``/store/addons/<slug>/update`` HTTP call returns. If we clear
    ``_attr_in_progress`` on that event while the coordinator data still
    carries the pre-update version, the UI briefly flips back to
    "Update available" before ``async_install`` can refresh. ``_update_ongoing``
    survives both the WS done event and the base ``UpdateEntity`` reset, so
    the installing state remains until the coordinator confirms a new
    ``installed_version``.
    """

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.BACKUP
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.PROGRESS
    )
    _update_ongoing: bool = False
    _version_before_update: str | None = None

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
    def in_progress(self) -> bool | None:
        """Return combined progress from the update job and refresh phase."""
        if self._update_ongoing:
            return True
        return self._attr_in_progress

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
        self._version_before_update = self.installed_version
        self._update_ongoing = True
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await update_addon(
                self.hass, self._addon_slug, backup, self.title, self.installed_version
            )
        except HomeAssistantError:
            self._update_ongoing = False
            self._version_before_update = None
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear the ongoing flag once the installed version has changed."""
        if (
            self._update_ongoing
            and self.installed_version != self._version_before_update
        ):
            self._update_ongoing = False
            self._version_before_update = None
        super()._handle_coordinator_update()

    @callback
    def _update_job_changed(self, job: Job) -> None:
        """Process update for this entity's update job."""
        if job.done is False:
            self._attr_in_progress = True
            self._attr_update_percentage = job.progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to progress updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.jobs.subscribe(
                JobSubscription(
                    self._update_job_changed,
                    name="addon_manager_update",
                    reference=self._addon_slug,
                )
            )
        )


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
        return "/api/brands/integration/homeassistant/icon.png?placeholder=no"

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
    """Update entity to handle updates for the Home Assistant Supervisor.

    The Supervisor update API blocks for the entire container download, then
    Supervisor restarts itself. The base UpdateEntity always resets
    ``_attr_in_progress`` after ``async_install`` returns, but at that point the
    restart is still ongoing. ``_update_ongoing`` survives that reset so the UI
    keeps showing the installing state until the coordinator refreshes with the
    new version after Supervisor comes back.
    """

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_title = "Home Assistant Supervisor"
    _update_ongoing: bool = False
    _version_before_update: str | None = None

    @property
    def in_progress(self) -> bool | None:
        """Return combined progress from the update job and restart phase."""
        if self._update_ongoing:
            return True
        return self._attr_in_progress

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
        return "/api/brands/integration/hassio/icon.png?placeholder=no"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._version_before_update = self.installed_version
        self._update_ongoing = True
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await self.coordinator.supervisor_client.supervisor.update()
        except SupervisorError as err:
            self._update_ongoing = False
            self._version_before_update = None
            self._attr_in_progress = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Error updating Home Assistant Supervisor: {err}"
            ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear the ongoing flag once the installed version has changed."""
        if (
            self._update_ongoing
            and self.installed_version != self._version_before_update
        ):
            self._update_ongoing = False
            self._version_before_update = None
        super()._handle_coordinator_update()

    @callback
    def _update_job_changed(self, job: Job) -> None:
        """Process update for this entity's update job."""
        if job.done is False:
            # Also covers updates not initiated via async_install (CLI,
            # Supervisor self-update): capture the baseline so the installing
            # state survives the Supervisor restart phase.
            if not self._update_ongoing:
                self._version_before_update = self.installed_version
                self._update_ongoing = True
            self._attr_in_progress = True
            self._attr_update_percentage = job.progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to progress updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.jobs.subscribe(
                JobSubscription(self._update_job_changed, name="supervisor_update")
            )
        )


class SupervisorCoreUpdateEntity(HassioCoreEntity, UpdateEntity):
    """Update entity to handle updates for Home Assistant Core."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.SPECIFIC_VERSION
        | UpdateEntityFeature.BACKUP
        | UpdateEntityFeature.PROGRESS
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
        return "/api/brands/integration/homeassistant/icon.png?placeholder=no"

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
        self._attr_in_progress = True
        self.async_write_ha_state()
        await update_core(self.hass, version, backup)

    @callback
    def _update_job_changed(self, job: Job) -> None:
        """Process update for this entity's update job."""
        if job.done is False:
            self._attr_in_progress = True
            self._attr_update_percentage = job.progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to progress updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.jobs.subscribe(
                JobSubscription(
                    self._update_job_changed, name="home_assistant_core_update"
                )
            )
        )
