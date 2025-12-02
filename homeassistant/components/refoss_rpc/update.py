"""Update entities for Refoss."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final, cast

from aiorefoss.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OTA_BEGIN, OTA_ERROR, OTA_PROGRESS, OTA_SUCCESS
from .coordinator import RefossConfigEntry, RefossCoordinator
from .entity import (
    RefossAttributeEntity,
    RefossEntityDescription,
    async_setup_entry_refoss,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RefossUpdateDescription(RefossEntityDescription, UpdateEntityDescription):
    """Class to describe a update."""

    latest_version: Callable[[dict], Any]


REFOSS_UPDATES: Final = {
    "fwupdate": RefossUpdateDescription(
        key="sys",
        sub_key="available_updates",
        name="Firmware",
        latest_version=lambda status: status.get("version", None),
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up update  for device."""
    async_setup_entry_refoss(
        hass, config_entry, async_add_entities, REFOSS_UPDATES, RefossUpdateEntity
    )


class RefossUpdateEntity(RefossAttributeEntity, UpdateEntity):
    """Refoss update entity."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    entity_description: RefossUpdateDescription

    def __init__(
        self,
        coordinator: RefossCoordinator,
        key: str,
        attribute: str,
        description: RefossUpdateDescription,
    ) -> None:
        """Initialize update entity."""
        super().__init__(coordinator, key, attribute, description)
        self._ota_in_progress = False
        self._ota_progress_percentage: int | None = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_subscribe_ota_events(self.firmware_upgrade_callback)
        )

    @callback
    def firmware_upgrade_callback(self, event: dict[str, Any]) -> None:
        """Handle device firmware upgrade  progress."""
        if self.in_progress is not False:
            event_type = event["event"]
            if event_type == OTA_BEGIN:
                self._ota_progress_percentage = 0
            elif event_type == OTA_PROGRESS:
                self._ota_progress_percentage = event["progress_percent"]
            elif event_type in (OTA_ERROR, OTA_SUCCESS):
                self._ota_in_progress = False
                self._ota_progress_percentage = None
            self.async_write_ha_state()

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return cast(str, self.coordinator.device.firmware_version)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        new_version = self.entity_description.latest_version(self.sub_status)
        if new_version:
            return cast(str, new_version)

        return self.installed_version

    @property
    def in_progress(self) -> bool:
        """Update installation in progress."""
        return self._ota_in_progress

    @property
    def update_percentage(self) -> int | None:
        """Update installation progress."""
        return self._ota_progress_percentage

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        update_data = self.coordinator.device.status["sys"]["available_updates"]
        LOGGER.debug("firmware update service - update_data: %s", update_data)

        new_version = update_data.get("version")

        LOGGER.info(
            "Starting firmware update of device %s from '%s' to '%s'",
            self.coordinator.name,
            self.coordinator.device.firmware_version,
            new_version,
        )
        try:
            await self.coordinator.device.trigger_firmware_update()
        except DeviceConnectionError as err:
            raise HomeAssistantError(
                f"firmware update connection error: {err!r}"
            ) from err
        except RpcCallError as err:
            raise HomeAssistantError(f"firmware update request error: {err!r}") from err
        except InvalidAuthError:
            await self.coordinator.async_shutdown_device_and_start_reauth()
        else:
            self._ota_in_progress = True
            self._ota_progress_percentage = None
            LOGGER.debug(
                "firmware update call for %s successful", self.coordinator.name
            )
