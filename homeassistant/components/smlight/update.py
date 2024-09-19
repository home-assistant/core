"""Support updates for SLZB-06 ESP32 and Zigbee firmwares."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from pysmlight.const import Events as SmEvents
from pysmlight.models import Firmware, Info
from pysmlight.sse import MessageEvent

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmConfigEntry
from .coordinator import SmFirmwareUpdateCoordinator, SmFwData
from .entity import SmEntity


@dataclass(frozen=True, kw_only=True)
class SmUpdateEntityDescription(UpdateEntityDescription):
    """Describes SMLIGHT SLZB-06 update entity."""

    installed_version: Callable[[Info], str | None]
    fw_list: Callable[[SmFwData], list[Firmware] | None]


UPDATE_ENTITIES: Final = [
    SmUpdateEntityDescription(
        key="core_update",
        translation_key="core_update",
        installed_version=lambda x: x.sw_version,
        fw_list=lambda x: x.esp_firmware,
    ),
    SmUpdateEntityDescription(
        key="zigbee_update",
        translation_key="zigbee_update",
        installed_version=lambda x: x.zb_version,
        fw_list=lambda x: x.zb_firmware,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: SmConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SMLIGHT update entities."""
    coordinator = entry.runtime_data.firmware

    async_add_entities(
        SmUpdateEntity(coordinator, description) for description in UPDATE_ENTITIES
    )


class SmUpdateEntity(SmEntity, UpdateEntity):
    """Representation for SLZB-06 update entities."""

    coordinator: SmFirmwareUpdateCoordinator
    entity_description: SmUpdateEntityDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(
        self,
        coordinator: SmFirmwareUpdateCoordinator,
        description: SmUpdateEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"

        self._finished_event = asyncio.Event()
        self._firmware: Firmware | None = None
        self._unload: list[Callable] = []

    @property
    def installed_version(self) -> str | None:
        """Version installed.."""
        data = self.coordinator.data

        version = self.entity_description.installed_version(data.info)
        return version if version != "-1" else None

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        data = self.coordinator.data
        if self.coordinator.legacy_api == 2:
            return None

        fw = self.entity_description.fw_list(data)

        if fw and self.entity_description.key == "zigbee_update":
            fw = [f for f in fw if f.type == data.info.zb_type]

        if fw:
            self._firmware = fw[0]
            return self._firmware.ver

        return None

    def register_callbacks(self) -> None:
        """Register callbacks for SSE update events."""
        self._unload.append(
            self.coordinator.client.sse.register_callback(
                SmEvents.ZB_FW_prgs, self._update_progress
            )
        )
        self._unload.append(
            self.coordinator.client.sse.register_callback(
                SmEvents.FW_UPD_done, self._update_finished
            )
        )
        if self.coordinator.legacy_api == 1:
            self._unload.append(
                self.coordinator.client.sse.register_callback(
                    SmEvents.ESP_UPD_done, self._update_finished
                )
            )
        self._unload.append(
            self.coordinator.client.sse.register_callback(
                SmEvents.ZB_FW_err, self._update_failed
            )
        )

    def release_notes(self) -> str | None:
        """Return release notes for firmware."""

        if self._firmware and self._firmware.notes:
            return self._firmware.notes

        return None

    @callback
    def _update_progress(self, progress: MessageEvent) -> None:
        """Update install progress on event."""

        progress = int(progress.data)
        if progress > 1:
            self._attr_in_progress = progress
            self.async_write_ha_state()

    def _update_done(self) -> None:
        """Handle cleanup for update done."""
        self._finished_event.set()
        self.coordinator.in_progress = False

        for remove_cb in self._unload:
            remove_cb()
        self._unload.clear()

    @callback
    def _update_finished(self, event: MessageEvent) -> None:
        """Handle event for update finished."""

        self._update_done()

    @callback
    def _update_failed(self, event: MessageEvent) -> None:
        self._update_done()

        raise HomeAssistantError(f"Update failed for {self.name}")

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install firmware update."""

        if not self.coordinator.in_progress and self._firmware:
            self.coordinator.in_progress = True
            self._attr_in_progress = True
            self.register_callbacks()

            await self.coordinator.client.fw_update(self._firmware)

            # block until update finished event received
            await self._finished_event.wait()

            await self.coordinator.async_refresh()
            self._finished_event.clear()
