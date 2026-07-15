"""Bosch Smart Home Camera — Update Platform.

Shows firmware update status using the native HA update entity.
Data source: GET /v11/video_inputs/{id}/firmware (short form).
Response: {current, upToDate, update, updating, status}

Install action: PUT /v11/video_inputs/{id}/firmware with {"id": <version>} —
the same endpoint/payload the official Bosch app's "Update now" button uses
(research/apk_2.12.0 decompile: FirmwareBackendService.UpdateCameraFirmware,
called with the GET response's own `update`/LatestFirmwareVersion field as
the "id" value). Bosch also rolls firmware out automatically on its own
schedule — this button lets the user install a pending update immediately
instead of waiting for that rollout.
"""

import logging
from typing import Any, override

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BoschCameraConfigEntry
from .base import _BoschEntityBase

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = config_entry.runtime_data
    entities = [
        BoschFirmwareUpdate(coordinator, cam_id, config_entry)
        for cam_id in coordinator.data
    ]
    async_add_entities(entities, update_before_add=False)


class BoschFirmwareUpdate(_BoschEntityBase, UpdateEntity):
    """Update entity showing camera firmware status."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    # PROGRESS: without it, HA's own async_install_with_progress() ignores our
    # in_progress property (below) and drives an internal in_progress flag
    # that is only True while async_install() is awaiting — i.e. for the
    # single PUT call, not the following minutes of on-camera flashing —
    # so the frontend's progress indicator vanished almost immediately.
    # With PROGRESS set, HA uses our in_progress property instead, which
    # stays True for as long as the coordinator's slow-tier poll reports
    # Bosch's own `updating` flag as true.
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_firmware_update"
        self._attr_translation_key = "firmware_update"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    @override
    def installed_version(self) -> str | None:
        fw: dict[str, Any] = self.coordinator.firmware_cache.get(self._cam_id, {})
        return fw.get("current") or self._fw or None

    @property
    @override
    def latest_version(self) -> str | None:
        fw: dict[str, Any] = self.coordinator.firmware_cache.get(self._cam_id, {})
        if not fw:
            return self.installed_version
        up_to_date: bool | None = fw.get("upToDate")
        if up_to_date is None:
            # Partial payload: upToDate key absent — indeterminate, do not claim up-to-date
            return None
        if up_to_date:
            return self.installed_version
        update_ver: str | None = fw.get("update")
        if update_ver:
            return update_ver
        # Not up to date but no update version specified
        return "update available"

    @property
    @override
    def in_progress(self) -> bool:
        fw: dict[str, Any] = self.coordinator.firmware_cache.get(self._cam_id, {})
        return bool(fw.get("updating", False))

    @property
    @override
    def available(self) -> bool:
        return bool(self.coordinator.last_update_success)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        fw: dict[str, Any] = self.coordinator.firmware_cache.get(self._cam_id, {})
        return {
            "up_to_date": fw.get("upToDate"),
            "updating": fw.get("updating", False),
            "status": fw.get("status", ""),
        }

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the pending firmware update now instead of waiting for Bosch's rollout.

        `version` is ignored — Bosch's firmware endpoint only ever offers a
        single next version (the `update` field), the same one the official
        app reads before calling this endpoint, so we always target that.

        Delegates to the coordinator's `async_install_firmware()` — shared
        with the "Fix" action on the `firmware_update_available` Repairs
        issue (repairs.py) so both entry points guard/write-lock identically
        instead of duplicating that logic.
        """
        await self.coordinator.async_install_firmware(self._cam_id)
