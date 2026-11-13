"""Support for Peblar updates."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from peblar import PackageType

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    PeblarConfigEntry,
    PeblarVersionDataUpdateCoordinator,
    PeblarVersionInformation,
)
from .entity import PeblarEntity
from .helpers import peblar_exception_handler

PARALLEL_UPDATES = 1


def _customization_update_pending(versions: PeblarVersionInformation) -> bool:
    """Return whether a customization package is waiting to be installed."""
    return (
        versions.available.customization is not None
        and versions.available.customization != versions.current.customization
    )


@dataclass(frozen=True, kw_only=True)
class PeblarUpdateEntityDescription(UpdateEntityDescription):
    """Describe an Peblar update entity."""

    available_fn: Callable[[PeblarVersionInformation], str | None]
    has_fn: Callable[[PeblarVersionInformation], bool] = lambda _: True
    installed_fn: Callable[[PeblarVersionInformation], str | None]
    package_type: PackageType


DESCRIPTIONS: tuple[PeblarUpdateEntityDescription, ...] = (
    PeblarUpdateEntityDescription(
        key="firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        package_type=PackageType.FIRMWARE,
        installed_fn=lambda x: x.current.firmware,
        has_fn=lambda x: x.available.firmware is not None,
        available_fn=lambda x: x.available.firmware,
    ),
    PeblarUpdateEntityDescription(
        key="customization",
        translation_key="customization",
        package_type=PackageType.CUSTOMIZATION,
        available_fn=lambda x: x.available.customization,
        has_fn=lambda x: x.available.customization is not None,
        installed_fn=lambda x: x.current.customization,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Peblar update based on a config entry."""
    async_add_entities(
        PeblarUpdateEntity(
            entry=entry,
            coordinator=entry.runtime_data.version_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
        if description.has_fn(entry.runtime_data.version_coordinator.data)
    )


class PeblarUpdateEntity(
    PeblarEntity[PeblarVersionDataUpdateCoordinator],
    UpdateEntity,
):
    """Defines a Peblar update entity."""

    entity_description: PeblarUpdateEntityDescription

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    @property
    @override
    def in_progress(self) -> bool:
        """Return whether the charger is busy installing a package.

        No percentage goes with it: the charger reports only whether an
        update succeeded, never how far along it is.
        """
        return self.coordinator.install_in_progress

    @property
    @override
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        return self.entity_description.installed_fn(self.coordinator.data)

    @property
    @override
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.entity_description.available_fn(self.coordinator.data)

    @peblar_exception_handler
    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the package the charger has on offer."""
        if self.entity_description.package_type is PackageType.FIRMWARE:
            await self._async_raise_if_customization_pending()

        await self.coordinator.peblar.update(
            package_type=self.entity_description.package_type
        )
        self.coordinator.async_refresh_after_restart()

    async def _async_raise_if_customization_pending(self) -> None:
        """Refuse firmware while a customization package is still waiting.

        Peblar's own web interface installs the customization package first
        and waits for the charger to come back before it touches the
        firmware. Doing it the other way around is not a sequence the
        charger is put through anywhere else.

        Versions are polled once every two hours, and the charger answers
        from its own cache unless told not to. Both are asked again here:
        a customization published since the last poll is exactly the case
        this refusal is for, and it would otherwise walk straight past it.
        """
        versions = PeblarVersionInformation(
            current=await self.coordinator.peblar.current_versions(),
            available=await self.coordinator.peblar.available_versions(use_cache=False),
        )

        if _customization_update_pending(versions):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="customization_update_first",
            )
