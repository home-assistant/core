"""Bosch Smart Home Camera — Button Platform.

Creates per-camera button entities:
  • {Name} Refresh Snapshot — forces an immediate coordinator refresh (data + image)
  • {Name} Restart Camera — soft-reset (reboot) via the Bosch cloud API
  • {Name} Factory Reset Camera — hard-reset via the Bosch cloud API (disabled by
    default — destructive, requires re-pairing the camera in the Bosch app)

The Live Stream is controlled by the switch platform (switch.py):
  switch.bosch_garten_live_stream  →  ON = open live proxy, OFF = close
"""

import logging
from typing import Any, override

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BoschCameraConfigEntry, get_options
from .base import _BoschEntityBase

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for each camera."""
    opts = get_options(config_entry)
    coordinator = config_entry.runtime_data
    entities: list[Any] = []
    if opts.get("enable_snapshot_button", True):
        entities.extend(
            BoschRefreshSnapshotButton(coordinator, cam_id, config_entry)
            for cam_id in coordinator.data
        )
    else:
        _LOGGER.debug("Snapshot button disabled in options — skipping")
    for cam_id in coordinator.data:
        entities.append(BoschSoftResetButton(coordinator, cam_id, config_entry))
        entities.append(BoschHardResetButton(coordinator, cam_id, config_entry))
    async_add_entities(entities, update_before_add=False)


# ─────────────────────────────────────────────────────────────────────────────
class BoschRefreshSnapshotButton(_BoschEntityBase, ButtonEntity):
    """Button: force an immediate coordinator refresh.

    Fetches latest camera info, status, and events from the Bosch Cloud API
    right now — without waiting for the next scheduled interval.
    Useful after motion events or when you want a fresh snapshot immediately.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the refresh-snapshot button."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_refresh_{cam_id.lower()}"
        self._attr_translation_key = "refresh_snapshot"

    @override
    async def async_press(self) -> None:
        """Force an immediate data refresh and image update for this camera."""
        _LOGGER.debug("Snapshot refresh triggered for %s", self._cam_title)
        # Fire coordinator refresh in background — do NOT await it.
        # async_request_refresh() awaits the full coordinator tick (can take 6-22 s);
        # blocking here makes the button feel frozen in the browser/card.
        task = self.hass.async_create_task(self.coordinator.async_request_refresh())
        task.add_done_callback(
            lambda t: (
                _LOGGER.warning(
                    "Snapshot refresh failed for %s: %s", self._cam_title, t.exception()
                )
                if not t.cancelled() and t.exception()
                else None
            )
        )
        # Refresh the camera image immediately (parallel, faster than coordinator tick)
        cam = self.coordinator.camera_entities.get(self._cam_id)
        if cam:
            img_task = self.hass.async_create_task(
                cam.async_trigger_image_refresh(delay=0)
            )
            img_task.add_done_callback(
                lambda t: (
                    _LOGGER.warning(
                        "Image refresh failed for %s: %s",
                        self._cam_title,
                        t.exception(),
                    )
                    if not t.cancelled() and t.exception()
                    else None
                )
            )


# ─────────────────────────────────────────────────────────────────────────────
class BoschSoftResetButton(_BoschEntityBase, ButtonEntity):
    """Button: reboot the camera (soft reset) via the Bosch cloud API.

    Same effect as the "Restart" action in the official Bosch app — the
    camera briefly drops offline while it reboots, then reconnects on its
    own. Non-destructive: no re-pairing needed afterward.

    Disabled by default (2026-07-08): live-tested against a real, online,
    owned Gen2 camera and Bosch's cloud rejected it with HTTP 404
    sh:entity.notfound, even though the request matches the decompiled
    Bosch app byte-for-byte (URL, base host, camera ID, empty body — a
    second independent code-review pass re-confirmed this). Most likely
    the endpoint isn't enabled server-side for every account/camera/
    firmware combination yet. Kept in the codebase (not reverted) since
    the implementation is correct and may simply start working once
    Bosch's backend catches up — re-enable manually to test.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the soft-reset button."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_soft_reset_{cam_id.lower()}"
        self._attr_translation_key = "soft_reset"

    @override
    async def async_press(self) -> None:
        """Reboot the camera."""
        _LOGGER.info("Soft reset (restart) triggered for %s", self._cam_title)
        await self.coordinator.async_soft_reset_camera(self._cam_id)


# ─────────────────────────────────────────────────────────────────────────────
class BoschHardResetButton(_BoschEntityBase, ButtonEntity):
    """Button: factory-reset the camera (hard reset) via the Bosch cloud API.

    Same effect as the "Factory Reset" action in the official Bosch app —
    DESTRUCTIVE: the camera loses its Bosch account pairing entirely and
    must be re-commissioned from scratch via the Bosch app before this
    integration can see it again. Disabled by default; enable deliberately
    in the entity settings before use.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: Any, cam_id: str, entry: ConfigEntry) -> None:
        """Initialize the hard-reset button."""
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_hard_reset_{cam_id.lower()}"
        self._attr_translation_key = "hard_reset"

    @override
    async def async_press(self) -> None:
        """Factory-reset the camera. Requires re-pairing afterward."""
        _LOGGER.warning(
            "Hard reset (factory reset) triggered for %s — camera will require "
            "re-pairing in the Bosch app",
            self._cam_title,
        )
        await self.coordinator.async_hard_reset_camera(self._cam_id)
