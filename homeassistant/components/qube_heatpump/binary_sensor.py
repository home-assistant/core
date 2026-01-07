"""Binary Sensor platform for Qube Heat Pump."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorEntity
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

HIDDEN_VENDOR_IDS = {
    "dout_threewayvlv_val",
    "dout_fourwayvlv_val",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Qube binary sensors."""
    data = entry.runtime_data
    hub = data.hub
    coordinator = data.coordinator
    apply_label = data.apply_label_in_name
    multi_device = data.multi_device

    entities: list[BinarySensorEntity] = []
    alarm_entities: list[EntityDef] = []
    for ent in hub.entities:
        if ent.platform != "binary_sensor":
            continue
        entities.append(
            QubeBinarySensor(coordinator, hub, apply_label, multi_device, ent)
        )
        if _is_alarm_entity(ent):
            alarm_entities.append(ent)

    if alarm_entities:
        entities.append(
            QubeAlarmStatusBinarySensor(
                coordinator,
                hub,
                apply_label,
                multi_device,
                alarm_entities,
            )
        )

    async_add_entities(entities)


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


class QubeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Qube binary sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        ent: EntityDef,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._ent = ent
        self._hub = hub
        self._label = hub.label or "qube1"
        self._show_label = bool(show_label)
        if ent.translation_key:
            manual_name = hub.get_friendly_name("binary_sensor", ent.translation_key)
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
            suffix = f"{ent.input_type or 'input'}_{ent.address}".lower()
            base_uid = f"qube_binary_{suffix}"
            self._attr_unique_id = (
                f"{base_uid}_{self._label}" if multi_device else base_uid
            )
        vendor_id = getattr(ent, "vendor_id", None)
        if vendor_id in HIDDEN_VENDOR_IDS:
            self._attr_entity_registry_visible_default = False
            self._attr_entity_registry_enabled_default = False
        if vendor_id:
            candidate = vendor_id
            if self._show_label:
                candidate = f"{candidate}_{self._label}"
            self._attr_suggested_object_id = _slugify(candidate)

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
        """Return True if the binary sensor is on."""
        key = (
            self._ent.unique_id
            or f"binary_sensor_{self._ent.input_type or self._ent.write_type}_{self._ent.address}"
        )
        val = self.coordinator.data.get(key)
        return None if val is None else bool(val)

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        desired = self._ent.vendor_id or self._attr_unique_id
        if (
            desired
            and self._show_label
            and not str(desired).startswith(f"{self._label}_")
        ):
            desired = f"{self._label}_{desired}"
        desired_slug = _slugify(str(desired)) if desired else None
        await _async_ensure_entity_id(self.hass, self.entity_id, desired_slug)


class QubeAlarmStatusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Aggregate binary sensor for Qube alarm status."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        alarm_entities: list[EntityDef],
    ) -> None:
        """Initialize the alarm status binary sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._label = hub.label or "qube1"
        self._show_label = bool(show_label)
        self._multi_device = bool(multi_device)
        self._tied_entities = list(alarm_entities)
        base_unique = "qube_alarm_sensors_state"
        self._attr_unique_id = (
            f"{base_unique}_{self._label}" if self._multi_device else base_unique
        )
        self._attr_translation_key = "qube_alarm_sensors_active"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:alarm-light"
        self._keys = [_entity_state_key(ent) for ent in alarm_entities]
        self._attr_suggested_object_id = "qube_alarm_sensors"
        if self._show_label:
            self._attr_suggested_object_id = f"{self._label}_qube_alarm_sensors"

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
    def is_on(self) -> bool:
        """Return True if any alarm is active."""
        data = self.coordinator.data or {}
        for key in self._keys:
            val = data.get(key)
            if isinstance(val, bool) and val:
                return True
        return False

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        desired = self._attr_suggested_object_id
        if desired:
            await _async_ensure_entity_id(self.hass, self.entity_id, _slugify(desired))


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_").lower()


def _is_alarm_entity(ent: EntityDef) -> bool:
    """Check if entity is an alarm."""
    if ent.platform != "binary_sensor":
        return False
    name = (ent.name or "").lower()
    if "alarm" in name:
        return True
    vendor = (ent.vendor_id or "").lower()
    return vendor.startswith("al")


def _entity_state_key(ent: EntityDef) -> str:
    """Generate state key for entity."""
    if ent.unique_id:
        return ent.unique_id
    suffix = f"{ent.input_type or ent.write_type}_{ent.address}"
    return f"binary_sensor_{suffix}"
