"""Support updates for SLZB-06 ESP32 and Zigbee firmwares."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import SmConfigEntry, SmFirmwareUpdateCoordinator, SmFwData
from .entity import SmEntity

PARALLEL_UPDATES = 1


def zigbee_latest_version(data: SmFwData, idx: int) -> Firmware | None:
    """Get the latest Zigbee firmware version."""

    if idx < len(data.zb_firmware):
        firmware_list = data.zb_firmware[idx]
        if firmware_list:
            return firmware_list[0]
    return None


@dataclass(frozen=True, kw_only=True)
class SmUpdateEntityDescription(UpdateEntityDescription):
    """Describes SMLIGHT SLZB-06 update entity."""

    installed_version: Callable[[Info, int], str | None]
    latest_version: Callable[[SmFwData, int], Firmware | None]


CORE_UPDATE_ENTITY = SmUpdateEntityDescription(
    key="core_update",
    translation_key="core_update",
    installed_version=lambda x, idx: x.sw_version,
    latest_version=lambda x, idx: x.esp_firmware[0] if x.esp_firmware else None,
)

ZB_UPDATE_ENTITY = SmUpdateEntityDescription(
    key="zigbee_update",
    translation_key="zigbee_update",
    installed_version=lambda x, idx: x.radios[idx].zb_version,
    latest_version=zigbee_latest_version,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SMLIGHT update entities."""
    coordinator = entry.runtime_data.firmware

    # updates not available for legacy API, user will get repair to update externally
    if coordinator.legacy_api == 2:
        return

    entities = [SmUpdateEntity(coordinator, CORE_UPDATE_ENTITY)]
    radios = coordinator.data.info.radios

    entities.extend(
        SmUpdateEntity(coordinator, ZB_UPDATE_ENTITY, idx)
        for idx, _ in enumerate(radios)
    )

    async_add_entities(entities)


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
        idx: int = 0,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = description
        device = description.key + (f"_{idx}" if idx else "")
        self._attr_unique_id = f"{coordinator.unique_id}-{device}"

        self._finished_event = asyncio.Event()
        self._firmware: Firmware | None = None
        self._unload: list[Callable] = []
        self.idx = idx

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update callbacks."""
        self._firmware = self.entity_description.latest_version(
            self.coordinator.data, self.idx
        )
        if self._firmware:
            self.async_write_ha_state()

    @property
    def installed_version(self) -> str | None:
        """Version installed.."""
        data = self.coordinator.data

        return self.entity_description.installed_version(data.info, self.idx)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""

        return self._firmware.ver if self._firmware else None

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
        if "zigbee" in self.entity_description.key:
            notes = f"### {'ZNP' if self.idx else 'EZSP'} Firmware\n\n"
        else:
            notes = "### Core Firmware\n\n"

        if self._firmware and self._firmware.notes:
            notes += self._firmware.notes
            return notes

        return None

    @callback
    def _update_progress(self, progress: MessageEvent) -> None:
        """Update install progress on event."""

        progress = int(progress.data)
        self._attr_update_percentage = progress
        self.async_write_ha_state()

    def _update_done(self) -> None:
        """Handle cleanup for update done."""
        self._finished_event.set()

        for remove_cb in self._unload:
            remove_cb()
        self._unload.clear()

        self._attr_in_progress = False
        self._attr_update_percentage = None
        self.async_write_ha_state()

    @callback
    def _update_finished(self, event: MessageEvent) -> None:
        """Handle event for update finished."""

        self._update_done()

    @callback
    def _update_failed(self, event: MessageEvent) -> None:
        self._update_done()
        self.coordinator.in_progress = False
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="firmware_update_failed",
            translation_placeholders={
                "device_name": str(self.name),
            },
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install firmware update."""

        if not self.coordinator.in_progress and self._firmware:
            self.coordinator.in_progress = True
            self._attr_in_progress = True
            self._attr_update_percentage = None
            self.register_callbacks()

            await self.coordinator.client.fw_update(self._firmware, self.idx)

            # block until update finished event received
            await self._finished_event.wait()

            # allow time for SLZB-06 to reboot before updating coordinator data
            try:
                async with asyncio.timeout(180):
                    while (
                        self.coordinator.in_progress
                        and self.installed_version != self._firmware.ver
                    ):
                        await self.coordinator.async_refresh()
                        await asyncio.sleep(1)
            except TimeoutError:
                LOGGER.warning(
                    "Timeout waiting for %s to reboot after update",
                    self.coordinator.data.info.hostname,
                )

            self.coordinator.in_progress = False
            self._finished_event.clear()
