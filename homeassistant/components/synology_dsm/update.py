"""Support for Synology DSM update platform."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, override

from synology_dsm.api.core.package import SynoCorePackage, SynoPackage
from synology_dsm.api.core.upgrade import SynoCoreUpgrade
from yarl import URL

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import SynoApi
from .const import HIDDEN_PACKAGE_INSTALL_TYPE
from .coordinator import SynologyDSMCentralUpdateCoordinator, SynologyDSMConfigEntry
from .entity import SynologyDSMBaseEntity, SynologyDSMEntityDescription

PACKAGE_RELEASE_NOTES_URL = "https://www.synology.com/en-global/releaseNote"


@dataclass(frozen=True, kw_only=True)
class SynologyDSMUpdateEntityEntityDescription(
    UpdateEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM update entity."""


UPDATE_ENTITIES: Final = [
    SynologyDSMUpdateEntityEntityDescription(
        api_key=SynoCoreUpgrade.API_KEY,
        key="update",
        translation_key="update",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]

PACKAGE_UPDATE_ENTITY: Final = SynologyDSMUpdateEntityEntityDescription(
    api_key=SynoCorePackage.API_KEY,
    key="package_update",
    translation_key="package_update",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SynologyDSMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Synology DSM update entities."""
    data = entry.runtime_data
    async_add_entities(
        SynoDSMUpdateEntity(data.api, data.coordinator_central, description)
        for description in UPDATE_ENTITIES
    )

    if data.api.package is None:
        return
    known_package_ids: set[str] = set()

    @callback
    def _async_add_new_packages() -> None:
        """Add entities for the packages installed since the last update."""
        if (package_api := data.api.package) is None:
            return
        new_packages = [
            package
            for package in package_api.get_all_packages()
            if package.package_id not in known_package_ids
            and package.install_type != HIDDEN_PACKAGE_INSTALL_TYPE
        ]
        known_package_ids.update(package.package_id for package in new_packages)
        async_add_entities(
            SynoDSMPackageUpdateEntity(data.api, data.coordinator_central, package)
            for package in new_packages
        )

    _async_add_new_packages()
    entry.async_on_unload(
        data.coordinator_central.async_add_listener(_async_add_new_packages)
    )


class SynoDSMUpdateEntity(
    SynologyDSMBaseEntity[SynologyDSMCentralUpdateCoordinator], UpdateEntity
):
    """Mixin for update entity specific attributes."""

    entity_description: SynologyDSMUpdateEntityEntityDescription
    _attr_title = "Synology DSM"

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.upgrade) and super().available

    @property
    @override
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        if TYPE_CHECKING:
            assert self._api.information is not None
        return self._api.information.version_string

    @property
    @override
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if TYPE_CHECKING:
            assert self._api.upgrade is not None
        if not self._api.upgrade.update_available:
            return self.installed_version
        return self._api.upgrade.available_version

    @property
    @override
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        if TYPE_CHECKING:
            assert self._api.information is not None
            assert self._api.upgrade is not None

        if (details := self._api.upgrade.available_version_details) is None:
            return None

        url = URL("http://update.synology.com/autoupdate/whatsnew.php")
        query = {"model": self._api.information.model}
        if details["nano"] > 0:
            query["update_version"] = f"{details['buildnumber']}-{details['nano']}"
        else:
            query["update_version"] = details["buildnumber"]

        return url.update_query(query).human_repr()


class SynoDSMPackageUpdateEntity(
    SynologyDSMBaseEntity[SynologyDSMCentralUpdateCoordinator], UpdateEntity
):
    """Update entity for an installed package."""

    entity_description: SynologyDSMUpdateEntityEntityDescription
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        api: SynoApi,
        coordinator: SynologyDSMCentralUpdateCoordinator,
        package: SynoPackage,
    ) -> None:
        """Initialize the package update entity."""
        super().__init__(api, coordinator, PACKAGE_UPDATE_ENTITY)
        self._package_id = package.package_id
        self._attr_unique_id += f"_{package.package_id}"
        self._attr_title = package.name
        self._attr_translation_placeholders = {"package_name": package.name}

    @property
    def _package(self) -> SynoPackage | None:
        """Return the package, None if it is no longer installed."""
        if TYPE_CHECKING:
            assert self._api.package is not None
        return self._api.package.get_package(self._package_id)

    @property
    @override
    def available(self) -> bool:
        """Return True if the package is still installed."""
        return super().available and self._package is not None

    @property
    @override
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        if TYPE_CHECKING:
            assert self._package is not None
        return self._package.version

    @property
    @override
    def latest_version(self) -> str | None:
        """Latest version available for install, None if unknown."""
        package = self._package
        if TYPE_CHECKING:
            assert package is not None
        if (update_available := package.update_available) is None:
            return None
        return package.available_version if update_available else package.version

    @property
    @override
    def release_url(self) -> str | None:
        """URL to the release notes, None if the package is not in the catalogue."""
        package = self._package
        if TYPE_CHECKING:
            assert package is not None
        if package.available_version is None:
            return None
        return f"{PACKAGE_RELEASE_NOTES_URL}/{package.package_id}"

    @override
    async def async_release_notes(self) -> str | None:
        """Return the HTML changelog of the available version."""
        if TYPE_CHECKING:
            assert self._package is not None
        return self._package.available_version_changelog
