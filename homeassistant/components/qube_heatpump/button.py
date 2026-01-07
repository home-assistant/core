"""Button entities for Qube Heat Pump."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import QubeConfigEntry
    from .hub import QubeHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube reload button."""
    data = entry.runtime_data
    hub = data.hub
    coordinator = data.coordinator
    version = data.version or "unknown"
    apply_label = data.apply_label_in_name
    multi_device = data.multi_device

    async_add_entities(
        [
            QubeReloadButton(
                coordinator,
                hub,
                entry.entry_id,
                apply_label,
                multi_device,
                version,
            ),
        ]
    )


async def _async_ensure_entity_id(
    hass: HomeAssistant, entity_id: str, desired_obj: str | None
) -> None:
    """Ensure the entity has the desired object ID."""
    if not desired_obj:
        return
    registry = er.async_get(hass)
    current = registry.async_get(entity_id)
    if not current:
        return
    desired_eid = f"{current.domain}.{desired_obj}"
    if current.entity_id == desired_eid:
        return
    if registry.async_get(desired_eid):
        return
    with contextlib.suppress(Exception):
        registry.async_update_entity(current.entity_id, new_entity_id=desired_eid)


class QubeReloadButton(CoordinatorEntity, ButtonEntity):
    """Button to reload the Qube integration."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        entry_id: str,
        show_label: bool,
        multi_device: bool,
        version: str,
    ) -> None:
        """Initialize the reload button."""
        super().__init__(coordinator)
        self._hub = hub
        self._entry_id = entry_id
        self._multi_device = bool(multi_device)
        self._version = version
        label = hub.label or "qube1"
        self._show_label = bool(show_label)
        self._attr_translation_key = "qube_reload"
        manual_name = hub.get_friendly_name("button", "qube_reload")
        if manual_name:
            self._attr_name = manual_name
            self._attr_has_entity_name = False
        else:
            self._attr_has_entity_name = True

        # Stable unique ID
        self._attr_unique_id = (
            f"qube_reload_{self._entry_id}" if self._multi_device else "qube_reload"
        )
        self._attr_entity_category = EntityCategory.CONFIG
        # Suggest a stable object_id reflecting multi-device label when needed
        base_object = "qube_reload"
        self._attr_suggested_object_id = (
            _slugify(f"{label}_{base_object}") if self._show_label else base_object
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=(self._hub.label or "Qube Heatpump"),
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    async def async_press(self) -> None:
        """Handle the button press to reload the config entry."""
        await self.hass.config_entries.async_reload(self._entry_id)

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        label = self._hub.label or "qube1"
        desired_obj = _slugify(
            f"qube_reload_{label}" if self._show_label else "qube_reload"
        )
        await _async_ensure_entity_id(self.hass, self.entity_id, desired_obj)


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_").lower()
