# pylint: disable=duplicate-code
"""Creates Update entities for the my-PV Home Assistant integration."""

import asyncio
import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyPVCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV update."""
    coordinator: MyPVCoordinator = config_entry.runtime_data
    entities = []

    if (
        coordinator.supports_command("firmware_update")
        and coordinator.supports_data("fwversion")
        and coordinator.supports_data("fwversionlatest")
    ):
        download_command = None
        if coordinator.supports_command("firmware_download"):
            download_command = "firmware_download"
        update_percentage_key = None
        if coordinator.supports_data("upd_percentage"):
            update_percentage_key = "upd_percentage"
        entity_description = MyPVUpdateEntityDescription(
            key="firmware",
            translation_key="firmware",
            device_class=UpdateDeviceClass.FIRMWARE,
            download_command=download_command,
            install_command="firmware_update",
            installed_version_key="fwversion",
            latest_version_key="fwversionlatest",
            update_percentage_key=update_percentage_key,
        )
        entities.append(
            MyPVCommandUpdate(
                coordinator,
                entity_description,
                config_entry.entry_id,
            )
        )

    async_add_entities(entities)


class MyPVUpdateEntityDescription(UpdateEntityDescription, frozen_or_thawed=True):
    """A class that describes my-PV update entities."""

    download_command: str | None = None
    install_command: str
    installed_version_key: str
    latest_version_key: str
    update_percentage_key: str | None = None


class MyPVCommandUpdate(CoordinatorEntity, UpdateEntity):
    """Base my-PV Update."""

    _attr_has_entity_name = True
    _attr_available = False

    coordinator: MyPVCoordinator
    entity_description: MyPVUpdateEntityDescription

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: MyPVUpdateEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the update."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"

        self.entity_description = entity_description

        if entity_description.install_command:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL
        if entity_description.update_percentage_key:
            self._attr_supported_features |= UpdateEntityFeature.PROGRESS

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        self._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.connected:
            self._attr_available = False
        else:
            installed_version = self.coordinator.get_data_value(
                self.entity_description.installed_version_key
            )
            latest_version = self.coordinator.get_data_value(
                self.entity_description.latest_version_key
            )

            if None in [installed_version, latest_version]:
                self._attr_available = False
            else:
                self._attr_installed_version = str(installed_version)
                self._attr_latest_version = str(latest_version)

                self._attr_available = True

                if self.in_progress and self.entity_description.update_percentage_key:
                    update_percentage = self.coordinator.get_data_value(
                        self.entity_description.update_percentage_key
                    )
                    self._attr_update_percentage = (
                        int(update_percentage)
                        if update_percentage is not None
                        else None
                    )

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
        _LOGGER.error("Updating %s", self.name)
        if not self.coordinator.connected:
            self._attr_available = False
        else:
            if (
                self.entity_description.download_command
                and await self.coordinator.send_command(
                    self.entity_description.download_command
                )
            ):
                self._attr_in_progress = True
                self._attr_update_percentage = 0

                # At some time implement timeout
                while True:
                    if self.update_percentage == 100:
                        break

                    await asyncio.sleep(1)

            await self.coordinator.send_command(self.entity_description.install_command)

            await self.coordinator.reload_config()

        self.async_write_ha_state()
