"""Support for La Marzocco update entities."""

import asyncio
from dataclasses import dataclass
from typing import Any

from pylamarzocco.const import FirmwareType, UpdateCommandStatus
from pylamarzocco.exceptions import RequestNotSuccessful

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription

PARALLEL_UPDATES = 1
MAX_UPDATE_WAIT = 150


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoUpdateEntityDescription(
    LaMarzoccoEntityDescription,
    UpdateEntityDescription,
):
    """Description of a La Marzocco update entities."""

    component: FirmwareType


ENTITIES: tuple[LaMarzoccoUpdateEntityDescription, ...] = (
    LaMarzoccoUpdateEntityDescription(
        key="machine_firmware",
        translation_key="machine_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        component=FirmwareType.MACHINE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoUpdateEntityDescription(
        key="gateway_firmware",
        translation_key="gateway_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        component=FirmwareType.GATEWAY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create update entities."""

    coordinator = entry.runtime_data.settings_coordinator
    async_add_entities(
        LaMarzoccoUpdateEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoUpdateEntity(LaMarzoccoEntity, UpdateEntity):
    """Entity representing the update state."""

    entity_description: LaMarzoccoUpdateEntityDescription
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )

    @property
    def installed_version(self) -> str:
        """Return the current firmware version."""
        return self.coordinator.device.settings.firmwares[
            self.entity_description.component
        ].build_version

    @property
    def latest_version(self) -> str:
        """Return the latest firmware version."""
        if available_update := self.coordinator.device.settings.firmwares[
            self.entity_description.component
        ].available_update:
            return available_update.build_version
        return self.installed_version

    @property
    def release_url(self) -> str | None:
        """Return the release notes URL."""
        return "https://support-iot.lamarzocco.com/firmware-updates/"

    def release_notes(self) -> str | None:
        """Return the release notes for the latest firmware version."""
        if available_update := self.coordinator.device.settings.firmwares[
            self.entity_description.component
        ].available_update:
            return available_update.change_log
        return None

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""

        self._attr_in_progress = True
        self.async_write_ha_state()

        counter = 0

        def _raise_timeout_error() -> None:  # to avoid TRY301
            raise TimeoutError("Update timed out")

        try:
            await self.coordinator.device.update_firmware()
            while (
                update_progress := await self.coordinator.device.get_firmware()
            ).command_status is UpdateCommandStatus.IN_PROGRESS:
                if counter >= MAX_UPDATE_WAIT:
                    _raise_timeout_error()
                self._attr_update_percentage = update_progress.progress_percentage
                self.async_write_ha_state()
                await asyncio.sleep(3)
                counter += 1

        except (TimeoutError, RequestNotSuccessful) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "key": self.entity_description.key,
                },
            ) from exc
        finally:
            self._attr_in_progress = False
            await self.coordinator.async_request_refresh()
