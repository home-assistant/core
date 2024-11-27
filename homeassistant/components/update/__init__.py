"""Component to allow for providing device or service updates."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from functools import lru_cache
import logging
from typing import Any, Final, final

from awesomeversion import AwesomeVersion, AwesomeVersionCompareException
from propcache import cached_property
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_PICTURE, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ABCCachedProperties, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_AUTO_UPDATE,
    ATTR_BACKUP,
    ATTR_DISPLAY_PRECISION,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_SKIPPED_VERSION,
    ATTR_TITLE,
    ATTR_UPDATE_PERCENTAGE,
    ATTR_VERSION,
    DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
    UpdateEntityFeature,
)

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[UpdateEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(minutes=15)


class UpdateDeviceClass(StrEnum):
    """Device class for update."""

    FIRMWARE = "firmware"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(UpdateDeviceClass))


__all__ = [
    "ATTR_BACKUP",
    "ATTR_INSTALLED_VERSION",
    "ATTR_LATEST_VERSION",
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

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Select entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[UpdateEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_INSTALL,
        {
            vol.Optional(ATTR_VERSION): cv.string,
            vol.Optional(ATTR_BACKUP, default=False): cv.boolean,
        },
        async_install,
        [UpdateEntityFeature.INSTALL],
    )

    component.async_register_entity_service(
        SERVICE_SKIP,
        None,
        async_skip,
    )
    component.async_register_entity_service(
        "clear_skipped",
        None,
        async_clear_skipped,
    )

    websocket_api.async_register_command(hass, websocket_release_notes)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


async def async_install(entity: UpdateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to validate the call."""
    # If version is not specified, but no update is available.
    if (version := service_call.data.get(ATTR_VERSION)) is None and (
        entity.installed_version == entity.latest_version
        or entity.latest_version is None
    ):
        raise HomeAssistantError(f"No update available for {entity.entity_id}")

    # If version is specified, but not supported by the entity.
    if (
        version is not None
        and UpdateEntityFeature.SPECIFIC_VERSION not in entity.supported_features_compat
    ):
        raise HomeAssistantError(
            f"Installing a specific version is not supported for {entity.entity_id}"
        )

    # If backup is requested, but not supported by the entity.
    if (
        backup := service_call.data[ATTR_BACKUP]
    ) and UpdateEntityFeature.BACKUP not in entity.supported_features_compat:
        raise HomeAssistantError(f"Backup is not supported for {entity.entity_id}")

    # Update is already in progress.
    if entity.in_progress is not False:
        raise HomeAssistantError(
            f"Update installation already in progress for {entity.entity_id}"
        )

    await entity.async_install_with_progress(version, backup)


async def async_skip(entity: UpdateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to validate the call."""
    if entity.auto_update:
        raise HomeAssistantError(
            f"Skipping update is not supported for {entity.entity_id}"
        )
    await entity.async_skip()


async def async_clear_skipped(entity: UpdateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to validate the call."""
    if entity.auto_update:
        raise HomeAssistantError(
            f"Clearing skipped update is not supported for {entity.entity_id}"
        )
    await entity.async_clear_skipped()


class UpdateEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes update entities."""

    device_class: UpdateDeviceClass | None = None
    display_precision: int = 0
    entity_category: EntityCategory | None = EntityCategory.CONFIG


@lru_cache(maxsize=256)
def _version_is_newer(latest_version: str, installed_version: str) -> bool:
    """Return True if latest_version is newer than installed_version."""
    return AwesomeVersion(latest_version) > installed_version


CACHED_PROPERTIES_WITH_ATTR_ = {
    "auto_update",
    "installed_version",
    "device_class",
    "display_precision",
    "in_progress",
    "latest_version",
    "release_summary",
    "release_url",
    "supported_features",
    "title",
    "update_percentage",
}


class UpdateEntity(
    RestoreEntity,
    metaclass=ABCCachedProperties,
    cached_properties=CACHED_PROPERTIES_WITH_ATTR_,
):
    """Representation of an update entity."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            ATTR_DISPLAY_PRECISION,
            ATTR_ENTITY_PICTURE,
            ATTR_IN_PROGRESS,
            ATTR_RELEASE_SUMMARY,
            ATTR_UPDATE_PERCENTAGE,
        }
    )

    entity_description: UpdateEntityDescription
    _attr_auto_update: bool = False
    _attr_installed_version: str | None = None
    _attr_device_class: UpdateDeviceClass | None
    _attr_display_precision: int
    _attr_in_progress: bool | int = False
    _attr_latest_version: str | None = None
    _attr_release_summary: str | None = None
    _attr_release_url: str | None = None
    _attr_state: None = None
    _attr_supported_features: UpdateEntityFeature = UpdateEntityFeature(0)
    _attr_title: str | None = None
    _attr_update_percentage: int | float | None = None
    __skipped_version: str | None = None
    __in_progress: bool = False

    @cached_property
    def auto_update(self) -> bool:
        """Indicate if the device or service has auto update enabled."""
        return self._attr_auto_update

    @cached_property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._attr_installed_version

    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class.

        For updates this is True if the entity has a device class.
        """
        return self.device_class is not None

    @cached_property
    def device_class(self) -> UpdateDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
    def display_precision(self) -> int:
        """Return number of decimal digits for display of update progress."""
        if hasattr(self, "_attr_display_precision"):
            return self._attr_display_precision
        if hasattr(self, "entity_description"):
            return self.entity_description.display_precision
        return 0

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the category of the entity, if any."""
        if hasattr(self, "_attr_entity_category"):
            return self._attr_entity_category
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_category
        if UpdateEntityFeature.INSTALL in self.supported_features_compat:
            return EntityCategory.CONFIG
        return EntityCategory.DIAGNOSTIC

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend.

        Update entities return the brand icon based on the integration
        domain by default.
        """
        return (
            f"https://brands.home-assistant.io/_/{self.platform.platform_name}/icon.png"
        )

    @cached_property
    def in_progress(self) -> bool | int | None:
        """Update installation progress.

        Needs UpdateEntityFeature.PROGRESS flag to be set for it to be used.

        Should return a boolean (True if in progress, False if not).
        """
        return self._attr_in_progress

    @cached_property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._attr_latest_version

    @cached_property
    def release_summary(self) -> str | None:
        """Summary of the release notes or changelog.

        This is not suitable for long changelogs, but merely suitable
        for a short excerpt update description of max 255 characters.
        """
        return self._attr_release_summary

    @cached_property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self._attr_release_url

    @cached_property
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @cached_property
    def title(self) -> str | None:
        """Title of the software.

        This helps to differentiate between the device or entity name
        versus the title of the software installed.
        """
        return self._attr_title

    @property
    def supported_features_compat(self) -> UpdateEntityFeature:
        """Return the supported features as UpdateEntityFeature.

        Remove this compatibility shim in 2025.1 or later.
        """
        features = self.supported_features
        if type(features) is int:  # noqa: E721
            new_features = UpdateEntityFeature(features)
            self._report_deprecated_supported_features_values(new_features)
            return new_features
        return features

    @cached_property
    def update_percentage(self) -> int | float | None:
        """Update installation progress.

        Needs UpdateEntityFeature.PROGRESS flag to be set for it to be used.

        Can either return a number to indicate the progress from 0 to 100% or None.
        """
        return self._attr_update_percentage

    @final
    async def async_skip(self) -> None:
        """Skip the current offered version to update."""
        if (latest_version := self.latest_version) is None:
            raise HomeAssistantError(f"Cannot skip an unknown version for {self.name}")
        if self.installed_version == latest_version:
            raise HomeAssistantError(f"No update available to skip for {self.name}")
        self.__skipped_version = latest_version
        self.async_write_ha_state()

    @final
    async def async_clear_skipped(self) -> None:
        """Clear the skipped version."""
        self.__skipped_version = None
        self.async_write_ha_state()

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update.

        Version can be specified to install a specific version. When `None`, the
        latest version needs to be installed.

        The backup parameter indicates a backup should be taken before
        installing the update.
        """
        await self.hass.async_add_executor_job(self.install, version, backup)

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update.

        Version can be specified to install a specific version. When `None`, the
        latest version needs to be installed.

        The backup parameter indicates a backup should be taken before
        installing the update.
        """
        raise NotImplementedError

    async def async_release_notes(self) -> str | None:
        """Return full release notes.

        This is suitable for a long changelog that does not fit in the release_summary
        property. The returned string can contain markdown.
        """
        return await self.hass.async_add_executor_job(self.release_notes)

    def release_notes(self) -> str | None:
        """Return full release notes.

        This is suitable for a long changelog that does not fit in the release_summary
        property. The returned string can contain markdown.
        """
        raise NotImplementedError

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        # We don't inline the `_version_is_newer` function because of caching
        return _version_is_newer(latest_version, installed_version)

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if (installed_version := self.installed_version) is None or (
            latest_version := self.latest_version
        ) is None:
            return None

        if latest_version == self.__skipped_version:
            return STATE_OFF
        if latest_version == installed_version:
            return STATE_OFF

        try:
            newer = self.version_is_newer(latest_version, installed_version)
        except AwesomeVersionCompareException:
            # Can't compare versions, already tried exact match
            return STATE_ON
        return STATE_ON if newer else STATE_OFF

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        if (release_summary := self.release_summary) is not None:
            release_summary = release_summary[:255]

        # If entity supports progress, return the in_progress value.
        # Otherwise, we use the internal progress value.
        if UpdateEntityFeature.PROGRESS in self.supported_features_compat:
            in_progress = self.in_progress
            update_percentage = self.update_percentage if in_progress else None
            if type(in_progress) is not bool and isinstance(in_progress, int):
                update_percentage = in_progress
                in_progress = True
        else:
            in_progress = self.__in_progress
            update_percentage = None

        installed_version = self.installed_version
        latest_version = self.latest_version
        skipped_version = self.__skipped_version
        # Clear skipped version in case it matches the current installed
        # version or the latest version diverged.
        if (installed_version is not None and skipped_version == installed_version) or (
            latest_version is not None and skipped_version != latest_version
        ):
            skipped_version = None
            self.__skipped_version = None

        return {
            ATTR_AUTO_UPDATE: self.auto_update,
            ATTR_DISPLAY_PRECISION: self.display_precision,
            ATTR_INSTALLED_VERSION: installed_version,
            ATTR_IN_PROGRESS: in_progress,
            ATTR_LATEST_VERSION: latest_version,
            ATTR_RELEASE_SUMMARY: release_summary,
            ATTR_RELEASE_URL: self.release_url,
            ATTR_SKIPPED_VERSION: skipped_version,
            ATTR_TITLE: self.title,
            ATTR_UPDATE_PERCENTAGE: update_percentage,
        }

    @final
    async def async_install_with_progress(
        self, version: str | None, backup: bool
    ) -> None:
        """Install update and handle progress if needed.

        Handles setting the in_progress state in case the entity doesn't
        support it natively.
        """
        if UpdateEntityFeature.PROGRESS not in self.supported_features_compat:
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


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "update/release_notes",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_release_notes(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the full release notes for a entity."""
    entity = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])

    if entity is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    if UpdateEntityFeature.RELEASE_NOTES not in entity.supported_features_compat:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_SUPPORTED,
            "Entity does not support release notes",
        )
        return

    connection.send_result(
        msg["id"],
        await entity.async_release_notes(),
    )
