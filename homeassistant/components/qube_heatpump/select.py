"""Select platform for Qube Heat Pump."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import QubeConfigEntry
    from .hub import EntityDef, QubeHub

_LOGGER = logging.getLogger(__name__)

SGREADY_OPTIONS = ["Off", "Block", "Plus", "Max"]
MODE_TO_BITS = {
    "Off": (False, False),
    "Block": (True, False),
    "Plus": (False, True),
    "Max": (True, True),
}
BITS_TO_MODE = {value: key for key, value in MODE_TO_BITS.items()}
DEFAULT_OPTION = "Off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube select entities."""
    data = entry.runtime_data
    hub = data.hub
    coordinator = data.coordinator
    version = data.version or "unknown"
    show_label = data.apply_label_in_name
    multi_device = data.multi_device

    sg_a = _find_switch(hub, "bms_sgready_a")
    sg_b = _find_switch(hub, "bms_sgready_b")

    if not sg_a or not sg_b:
        _LOGGER.debug("SG Ready switches missing; skipping select entity creation")
        return

    async_add_entities(
        [
            QubeSGReadyModeSelect(
                coordinator,
                hub,
                show_label,
                multi_device,
                version,
                sg_a,
                sg_b,
                entry.entry_id,
            )
        ]
    )


def _find_switch(hub: QubeHub, vendor_id: str) -> EntityDef | None:
    for ent in hub.entities:
        if ent.platform != "switch":
            continue
        if (ent.vendor_id or "").lower() == vendor_id.lower():
            return ent
    return None


class QubeSGReadyModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for SG Ready mode."""

    _attr_should_poll = False
    _attr_options = SGREADY_OPTIONS

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
        sgready_a: EntityDef,
        sgready_b: EntityDef,
        entry_id: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._version = str(version) if version else "unknown"
        self._show_label = bool(show_label)
        self._multi_device = bool(multi_device)
        self._label = hub.label or "qube1"
        self._ent_a = sgready_a
        self._ent_b = sgready_b
        self._key_a = self._entity_key(sgready_a)
        self._key_b = self._entity_key(sgready_b)
        self._assumed_option = DEFAULT_OPTION
        self._entry_id = entry_id

        self._attr_translation_key = "sgready_mode"
        manual_name = hub.get_friendly_name("select", "sgready_mode")
        if manual_name:
            self._attr_name = manual_name
            self._attr_has_entity_name = False
        else:
            self._attr_has_entity_name = True
        unique_base = "sgready_mode"
        if self._multi_device:
            unique_base = f"{unique_base}_{self._entry_id}"
        self._attr_unique_id = unique_base
        suggested = "sgready_mode"
        if self._show_label:
            suggested = _slugify(f"{self._label}_{suggested}")
        self._attr_suggested_object_id = suggested

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

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        derived = self._derive_option()
        if derived is None:
            return self._assumed_option
        if derived != self._assumed_option:
            self._assumed_option = derived
        return derived

    async def async_select_option(self, option: str) -> None:
        """Select a new option."""
        if option not in MODE_TO_BITS:
            raise ValueError(f"Unsupported SG Ready mode: {option}")
        target_a, target_b = MODE_TO_BITS[option]
        current_a = self._read_bool(self._key_a)
        current_b = self._read_bool(self._key_b)

        await self._hub.async_connect()
        if current_a is None or current_a != target_a:
            await self._hub.async_write_switch(self._ent_a, target_a)
        if current_b is None or current_b != target_b:
            await self._hub.async_write_switch(self._ent_b, target_b)

        self._assumed_option = option
        await self.coordinator.async_request_refresh()

    def _derive_option(self) -> str | None:
        current_a = self._read_bool(self._key_a)
        current_b = self._read_bool(self._key_b)
        if current_a is None or current_b is None:
            return None
        return BITS_TO_MODE.get((current_a, current_b), DEFAULT_OPTION)

    def _read_bool(self, key: str) -> bool | None:
        value = self.coordinator.data.get(key)
        if value is None:
            return None
        try:
            return bool(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _entity_key(ent: EntityDef) -> str:
        if ent.unique_id:
            return ent.unique_id
        suffix = f"{ent.input_type or ent.write_type}_{ent.address}"
        return f"switch_{suffix}"

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired = self._attr_suggested_object_id or "sgready_mode"
        await _async_ensure_entity_id(self.hass, self.entity_id, desired)


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


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_").lower()
