"""Swing2Sleep Smarla Update platform."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pysmarlaapi import Federwiege
from pysmarlaapi.federwiege.services.classes import Property
from pysmarlaapi.federwiege.services.types import UpdateStatus

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FederwiegeConfigEntry
from .entity import SmarlaBaseEntity, SmarlaEntityDescription

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SmarlaUpdateEntityDescription(SmarlaEntityDescription, UpdateEntityDescription):
    """Class describing Swing2Sleep Smarla update entity."""


UPDATE_ENTITY_DESC = SmarlaUpdateEntityDescription(
    key="update",
    service="info",
    property="version",
    device_class=UpdateDeviceClass.FIRMWARE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FederwiegeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Smarla update entity based on a config entry."""
    federwiege = config_entry.runtime_data
    async_add_entities([SmarlaUpdate(federwiege, UPDATE_ENTITY_DESC)], True)


class SmarlaUpdate(SmarlaBaseEntity, UpdateEntity):
    """Defines an Smarla update entity."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_should_poll = True

    entity_description: SmarlaUpdateEntityDescription

    _property: Property[str]
    _update_property: Property[int]
    _update_status_property: Property[UpdateStatus]

    def __init__(
        self, federwiege: Federwiege, desc: SmarlaUpdateEntityDescription
    ) -> None:
        """Initialize the update entity."""
        super().__init__(federwiege, desc)
        self._update_property = federwiege.get_property("system", "firmware_update")
        self._update_status_property = federwiege.get_property(
            "system", "firmware_update_status"
        )

    async def async_update(self) -> None:
        """Check for firmware update and update attributes."""
        value = await self._federwiege.check_firmware_update()
        if value is None:
            self._attr_latest_version = None
            self._attr_release_summary = None
            return

        target, notes = value

        self._attr_latest_version = target
        self._attr_release_summary = notes

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        await self._update_status_property.add_listener(self.on_change)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        await super().async_will_remove_from_hass()
        await self._update_status_property.remove_listener(self.on_change)

    @property
    def in_progress(self) -> bool | None:
        """Return if an update is in progress."""
        status = self._update_status_property.get()
        return status not in (None, UpdateStatus.IDLE, UpdateStatus.FAILED)

    @property
    def installed_version(self) -> str | None:
        """Return the current installed version."""
        return self._property.get()

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install latest update."""
        self._update_property.set(1)
