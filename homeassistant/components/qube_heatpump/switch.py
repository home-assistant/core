"""Switch platform for Qube Heat Pump."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import QubeConfigEntry
    from .hub import EntityDef, QubeHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Qube switches."""
    data = entry.runtime_data
    hub = data.hub
    coordinator = data.coordinator
    apply_label = data.apply_label_in_name
    multi_device = data.multi_device

    entities: list[SwitchEntity] = []
    for ent in hub.entities:
        if ent.platform != "switch":
            continue
        if ent.vendor_id in {"bms_sgready_a", "bms_sgready_b"}:
            continue
        entities.append(QubeSwitch(coordinator, hub, apply_label, multi_device, ent))

    async_add_entities(entities)

    # Cleanup deprecated SG Ready entities
    registry = er.async_get(hass)
    to_remove_base = ["bms_sgready_a", "bms_sgready_b"]
    for base in to_remove_base:
        uid = f"{base}_{entry.entry_id}" if multi_device else base
        entity_id = registry.async_get_entity_id("switch", DOMAIN, uid)
        if entity_id:
            registry.async_remove(entity_id)


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


class QubeSwitch(CoordinatorEntity, SwitchEntity):
    """Qube switch entity."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        ent: EntityDef,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._ent = ent
        self._hub = hub
        self._show_label = bool(show_label)
        if ent.vendor_id in {"bms_sgready_a", "bms_sgready_b"}:
            self._attr_entity_registry_visible_default = False
            self._attr_entity_category = EntityCategory.CONFIG
        if ent.translation_key:
            manual_name = hub.get_friendly_name("switch", ent.translation_key)
            if manual_name:
                self._attr_name = manual_name
                self._attr_has_entity_name = False
            else:
                self._attr_translation_key = ent.translation_key
                self._attr_has_entity_name = True
        else:
            self._attr_name = str(ent.name)
        if ent.unique_id:
            self._attr_unique_id = ent.unique_id
        else:
            suffix = f"{ent.write_type or 'coil'}_{ent.address}".lower()
            base_uid = f"qube_switch_{suffix}"
            self._attr_unique_id = (
                f"{base_uid}_{self._hub.label}" if multi_device else base_uid
            )
        if getattr(ent, "vendor_id", None):
            candidate = ent.vendor_id
            if self._show_label:
                candidate = f"{candidate}_{self._hub.label}"
            self._attr_suggested_object_id = _slugify(str(candidate))

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=(self._hub.label or "Qube Heatpump"),
            manufacturer="Qube",
            model="Heatpump",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        key = (
            self._ent.unique_id
            or f"switch_{self._ent.input_type or self._ent.write_type}_{self._ent.address}"
        )
        val = self.coordinator.data.get(key)
        return None if val is None else bool(val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._hub.async_connect()
        await self._hub.async_write_switch(self._ent, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._hub.async_connect()
        await self._hub.async_write_switch(self._ent, False)
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired = self._ent.vendor_id or self._attr_unique_id
        if (
            desired
            and self._show_label
            and not str(desired).startswith(f"{self._hub.label}_")
        ):
            desired = f"{self._hub.label}_{desired}"
        desired_slug = _slugify(str(desired)) if desired else None
        await _async_ensure_entity_id(self.hass, self.entity_id, desired_slug)


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_").lower()
