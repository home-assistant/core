"""Component to allow for providing device or service updates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Final, final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BACKUP,
    ATTR_CURRENT_VERSION,
    ATTR_IN_PROGRESS,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_SKIPPED_VERSION,
    ATTR_TITLE,
    ATTR_VERSION,
    DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
    UpdateEntityFeature,
)

SCAN_INTERVAL = timedelta(minutes=15)

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

_LOGGER = logging.getLogger(__name__)


class UpdateDeviceClass(StrEnum):
    """Device class for update."""

    FIRMWARE = "firmware"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(UpdateDeviceClass))


__all__ = [
    "ATTR_BACKUP",
    "ATTR_VERSION",
    "DEVICE_CLASSES_SCHEMA",
    "DOMAIN",
    "PLATFORM_SCHEMA_BASE",
    "PLATFORM_SCHEMA",
    "SERVICE_INSTALL",
    "SERVICE_SKIP",
    "UpdateDeviceClass",
    "UpdateEntity",
    "UpdateEntityDescription",
    "UpdateEntityFeature",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Select entities."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_INSTALL,
        {
            vol.Optional(ATTR_VERSION): cv.string,
            vol.Optional(ATTR_BACKUP): cv.boolean,
        },
        async_install,
        [UpdateEntityFeature.INSTALL],
    )

    component.async_register_entity_service(
        SERVICE_SKIP,
        {},
        UpdateEntity.async_skip.__name__,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


async def async_install(entity: UpdateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to validate the call."""
    # If version is not specified, but no update is available.
    if (version := service_call.data.get(ATTR_VERSION)) is None and (
        entity.current_version == entity.latest_version or entity.latest_version is None
    ):
        raise HomeAssistantError(f"No update available for {entity.name}")

    # If version is specified, but not supported by the entity.
    if (
        version is not None
        and not entity.supported_features & UpdateEntityFeature.SPECIFIC_VERSION
    ):
        raise HomeAssistantError(
            f"Installing a specific version is not supported for {entity.name}"
        )

    # If backup is requested, but not supported by the entity.
    if (
        backup := service_call.data.get(ATTR_BACKUP)
    ) and not entity.supported_features & UpdateEntityFeature.BACKUP:
        raise HomeAssistantError(f"Backup is not supported for {entity.name}")

    # Update is already in progress.
    if entity.in_progress is not False:
        raise HomeAssistantError(
            f"Update installation already in progress for {entity.name}"
        )

    await entity.async_install_with_progress(version, backup)


@dataclass
class UpdateEntityDescription(EntityDescription):
    """A class that describes update entities."""

    device_class: UpdateDeviceClass | str | None = None
    entity_category: EntityCategory | None = EntityCategory.CONFIG


class UpdateEntity(RestoreEntity):
    """Representation of an update entity."""

    entity_description: UpdateEntityDescription
    _attr_current_version: str | None = None
    _attr_device_class: UpdateDeviceClass | str | None
    _attr_in_progress: bool | int = False
    _attr_latest_version: str | None = None
    _attr_release_summary: str | None = None
    _attr_release_url: str | None = None
    _attr_state: None = None
    _attr_supported_features: int = 0
    _attr_title: str | None = None
    __skipped_version: str | None = None
    __in_progress: bool = False

    @property
    def current_version(self) -> str | None:
        """Version currently in use."""
        return self._attr_current_version

    @property
    def device_class(self) -> UpdateDeviceClass | str | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    def entity_category(self) -> EntityCategory | str | None:
        """Return the category of the entity, if any."""
        if hasattr(self, "_attr_entity_category"):
            return self._attr_entity_category
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_category
        return EntityCategory.CONFIG

    @property
    def in_progress(self) -> bool | int | None:
        """Update installation progress.

        Needs UpdateEntityFeature.PROGRESS flag to be set for it to be used.

        Can either return a boolean (True if in progress, False if not)
        or an integer to indicate the progress in from 0 to 100%.
        """
        return self._attr_in_progress

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._attr_latest_version

    @property
    def release_summary(self) -> str | None:
        """Summary of the release notes or changelog.

        This is not suitable for long changelogs, but merely suitable
        for a short excerpt update description of max 255 characters.
        """
        return self._attr_release_summary

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self._attr_release_url

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def title(self) -> str | None:
        """Title of the software.

        This helps to differentiate between the device or entity name
        versus the title of the software installed.
        """
        return self._attr_title

    @final
    async def async_skip(self) -> None:
        """Skip the current offered version to update."""
        if (latest_version := self.latest_version) is None:
            raise HomeAssistantError(f"Cannot skip an unknown version for {self.name}")
        if self.current_version == latest_version:
            raise HomeAssistantError(f"No update available to skip for {self.name}")
        self.__skipped_version = latest_version
        self.async_write_ha_state()

    async def async_install(
        self,
        version: str | None = None,
        backup: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Install an update.

        Version can be specified to install a specific version. When `None`, the
        latest version needs to be installed.

        The backup parameter indicates a backup should be taken before
        installing the update.
        """
        await self.hass.async_add_executor_job(self.install, version, backup)

    def install(
        self,
        version: str | None = None,
        backup: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Install an update.

        Version can be specified to install a specific version. When `None`, the
        latest version needs to be installed.

        The backup parameter indicates a backup should be taken before
        installing the update.
        """
        raise NotImplementedError()

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if (current_version := self.current_version) is None or (
            latest_version := self.latest_version
        ) is None:
            return None

        if latest_version not in (current_version, self.__skipped_version):
            return STATE_ON
        return STATE_OFF

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        if (release_summary := self.release_summary) is not None:
            release_summary = release_summary[:255]

        # If entity supports progress, return the in_progress value.
        # Otherwise, we use the internal progress value.
        if self.supported_features & UpdateEntityFeature.PROGRESS:
            in_progress = self.in_progress
        else:
            in_progress = self.__in_progress

        # Clear skipped version in case it matches the current version or
        # the latest version diverged.
        if (
            self.__skipped_version == self.current_version
            or self.__skipped_version != self.latest_version
        ):
            self.__skipped_version = None

        return {
            ATTR_CURRENT_VERSION: self.current_version,
            ATTR_IN_PROGRESS: in_progress,
            ATTR_LATEST_VERSION: self.latest_version,
            ATTR_RELEASE_SUMMARY: release_summary,
            ATTR_RELEASE_URL: self.release_url,
            ATTR_SKIPPED_VERSION: self.__skipped_version,
            ATTR_TITLE: self.title,
        }

    @final
    async def async_install_with_progress(
        self,
        version: str | None = None,
        backup: bool | None = None,
    ) -> None:
        """Install update and handle progress if needed.

        Handles setting the in_progress state in case the entity doesn't
        support it natively.
        """
        if not self.supported_features & UpdateEntityFeature.PROGRESS:
            self.__in_progress = True
            self.async_write_ha_state()

        try:
            await self.async_install(version, backup)
        finally:
            # No matter what happens, we always stop progress in the end
            self._attr_in_progress = False
            self.__in_progress = False
            self.async_write_ha_state()

    async def async_internal_added_to_hass(self) -> None:
        """Call when the update entity is added to hass.

        It is used to restore the skipped version, if any.
        """
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.attributes.get(ATTR_SKIPPED_VERSION) is not None:
            self.__skipped_version = state.attributes[ATTR_SKIPPED_VERSION]
