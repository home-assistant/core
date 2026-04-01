"""Remote entity registry synchronization helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ...api import HomeAssistantAPI
from ...exceptions import FailedCommand, NotConnected
from ..core import context_from_payload, parse_datetime

from homeassistant.const import EntityCategory
from homeassistant.core import EventOrigin, HomeAssistant
from homeassistant.helpers import entity_registry as er


def _build_registry_entry(payload: Mapping[str, Any]) -> er.RegistryEntry:
    """Build a local entity registry entry from a websocket payload."""
    return er.RegistryEntry(
        aliases=list(payload["aliases"]),
        area_id=payload["area_id"],
        categories=dict(payload["categories"]),
        capabilities=payload["capabilities"],
        config_entry_id=payload["config_entry_id"],
        config_subentry_id=payload["config_subentry_id"],
        created_at=parse_datetime(payload["created_at"]),
        device_class=payload["device_class"],
        device_id=payload["device_id"],
        disabled_by=er.RegistryEntryDisabler(payload["disabled_by"])
        if payload["disabled_by"]
        else None,
        entity_category=EntityCategory(payload["entity_category"])
        if payload["entity_category"]
        else None,
        entity_id=payload["entity_id"].lower(),
        hidden_by=er.RegistryEntryHider(payload["hidden_by"])
        if payload["hidden_by"]
        else None,
        icon=payload["icon"],
        id=payload["id"],
        has_entity_name=payload["has_entity_name"],
        labels=set(payload["labels"]),
        modified_at=parse_datetime(payload["modified_at"]),
        name=payload["name"],
        object_id_base=payload["original_name"],
        options=payload["options"],
        original_device_class=payload["original_device_class"],
        original_icon=payload["original_icon"],
        original_name=payload["original_name"],
        platform=payload["platform"],
        suggested_object_id=None,
        supported_features=0,
        translation_key=payload["translation_key"],
        unique_id=payload["unique_id"],
        previous_unique_id=None,
        unit_of_measurement=None,
    )


class RemoteEntityRegistryManager:
    """Synchronize the local entity registry with a remote Home Assistant."""

    __slots__ = (
        "_hass",
        "_remote_entity_registry_ids",
        "_unsubscribe",
    )

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the remote entity registry manager."""
        self._hass = hass
        self._remote_entity_registry_ids: set[str] = set()
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def remote_api(self) -> HomeAssistantAPI | None:
        """Return the live remote API bound to the runtime."""
        return getattr(self._hass, "remote_api", None)

    async def async_setup(self) -> None:
        """Fetch the initial snapshot and subscribe to updates."""
        remote_api = self.remote_api
        if remote_api is None or self._unsubscribe is not None:
            return

        await self.async_refresh()
        self._unsubscribe = await remote_api.subscribe_events(
            self._handle_event,
            er.EVENT_ENTITY_REGISTRY_UPDATED,
        )

    def unsubscribe(self) -> None:
        """Cancel the remote entity registry subscription."""
        if self._unsubscribe is None:
            return
        unsubscribe = self._unsubscribe
        self._unsubscribe = None
        unsubscribe()

    async def _async_get_registry(self) -> er.EntityRegistry:
        """Return a loaded local entity registry."""
        registry = er.async_get(self._hass)
        if not hasattr(registry, "entities"):
            await registry.async_load(load_empty=True)
        return registry

    async def async_refresh(self) -> None:
        """Fetch the remote entity registry snapshot."""
        remote_api = self.remote_api
        if remote_api is None:
            return

        registry = await self._async_get_registry()
        entries = await remote_api.async_get_entity_registry()
        remote_ids: set[str] = set()

        for partial_entry in entries:
            entity_id = partial_entry["entity_id"].lower()
            try:
                full_entry = await remote_api.async_get_entity_registry_entry(entity_id)
            except FailedCommand:
                continue
            entry = _build_registry_entry(full_entry)
            registry.entities[entry.entity_id] = entry
            remote_ids.add(entry.entity_id)

        for entity_id in self._remote_entity_registry_ids - remote_ids:
            registry.entities.pop(entity_id, None)

        registry._entities_data = registry.entities.data
        self._remote_entity_registry_ids = remote_ids

    async def _handle_event(self, message: dict[str, Any]) -> None:
        """Apply a remote entity_registry_updated event locally."""
        event = message["event"]
        data = dict(event["data"])
        context = context_from_payload(event.get("context"))
        registry = await self._async_get_registry()
        action = data["action"]
        entity_id = data["entity_id"].lower()
        remote_api = self.remote_api

        if action == "remove":
            registry.entities.pop(entity_id, None)
            registry._entities_data = registry.entities.data
            self._remote_entity_registry_ids.discard(entity_id)
        else:
            try:
                assert remote_api is not None
                payload = await remote_api.async_get_entity_registry_entry(entity_id)
            except (FailedCommand, NotConnected):
                if action == "create":
                    return
            else:
                entry = _build_registry_entry(payload)
                old_entity_id = data.get("old_entity_id")
                if old_entity_id and old_entity_id in registry.entities:
                    registry.entities.pop(old_entity_id, None)
                    self._remote_entity_registry_ids.discard(old_entity_id)
                registry.entities[entry.entity_id] = entry
                registry._entities_data = registry.entities.data
                self._remote_entity_registry_ids.add(entry.entity_id)

        self._hass.bus.async_fire_internal(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            data,
            origin=EventOrigin.remote,
            context=context,
            time_fired=parse_datetime(event.get("time_fired")).timestamp(),
        )
