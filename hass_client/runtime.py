"""Remote-capable Home Assistant runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime
import logging
from typing import Any

from .api import HomeAssistantAPI
from .config import RemoteConfig
from .exceptions import FailedCommand, NotConnected

LOGGER = logging.getLogger(__name__)

try:
    from homeassistant.const import (
        ATTR_DOMAIN,
        ATTR_SERVICE,
        ATTR_SERVICE_DATA,
        EVENT_CALL_SERVICE,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
        EVENT_STATE_CHANGED,
        EVENT_STATE_REPORTED,
        EntityCategory,
    )
    from homeassistant.core import (
        Context,
        EventOrigin,
        HomeAssistant as CoreHomeAssistant,
        ServiceCall,
        ServiceRegistry,
        ServiceResponse,
        State,
        callback,
    )
    from homeassistant.exceptions import ServiceNotFound, ServiceValidationError
    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import dt as dt_util
except ImportError as err:  # pragma: no cover - guarded by core test environment
    raise RuntimeError(
        "hass-client requires Home Assistant core to be importable"
    ) from err


def _parse_datetime(value: float | str | None) -> datetime:
    """Parse a Home Assistant timestamp."""
    if isinstance(value, int | float):
        return dt_util.utc_from_timestamp(float(value))
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            return parsed
    return dt_util.utcnow()


def _context_from_payload(payload: Mapping[str, Any] | None) -> Context | None:
    """Build a Home Assistant context from websocket payload data."""
    if not payload:
        return None
    return Context(
        user_id=payload.get("user_id"),
        parent_id=payload.get("parent_id"),
        id=payload.get("id"),
    )


class HybridServiceRegistry(ServiceRegistry):
    """Local service registry with remote fallback."""

    __slots__ = ("_remote_api", "_remote_services")

    def __init__(
        self,
        hass: CoreHomeAssistant,
        remote_api: HomeAssistantAPI | None,
    ) -> None:
        """Initialize the hybrid service registry."""
        super().__init__(hass)
        self._remote_api = remote_api
        self._remote_services: dict[str, dict[str, dict[str, Any]]] = {}

    @callback
    def async_set_remote_services(self, services: Mapping[str, Mapping[str, Any]]) -> None:
        """Replace the remote service cache."""
        self._remote_services = {
            domain.lower(): {
                service.lower(): dict(description)
                for service, description in domain_services.items()
            }
            for domain, domain_services in services.items()
        }

    @callback
    def async_remote_services(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return a copy of the remote service cache."""
        return {
            domain: services.copy() for domain, services in self._remote_services.items()
        }

    def has_service(self, domain: str, service: str) -> bool:
        """Return if a local or remote service exists."""
        if super().has_service(domain, service):
            return True
        return service.lower() in self._remote_services.get(domain.lower(), {})

    async def async_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        blocking: bool = False,
        context: Context | None = None,
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> ServiceResponse:
        """Call a local service, then fall back to the remote websocket API."""
        try:
            return await super().async_call(
                domain=domain,
                service=service,
                service_data=service_data,
                blocking=blocking,
                context=context,
                target=target,
                return_response=return_response,
            )
        except ServiceNotFound:
            if self._remote_api is None or not self._remote_api.connected:
                raise

        context = context or Context()
        merged_service_data = dict(service_data or {})
        if target:
            merged_service_data.update(target)

        service_call = ServiceCall(
            self._hass,
            domain.lower(),
            service.lower(),
            merged_service_data,
            context=context,
            return_response=return_response,
        )

        async def _remote_call() -> dict[str, Any]:
            assert self._remote_api is not None
            response = await self._remote_api.async_call_service(
                domain=domain,
                service=service,
                service_data=service_data,
                target=target,
                return_response=return_response,
            )
            self._hass.bus.async_fire_internal(
                EVENT_CALL_SERVICE,
                {
                    ATTR_DOMAIN: domain.lower(),
                    ATTR_SERVICE: service.lower(),
                    ATTR_SERVICE_DATA: merged_service_data,
                },
                context=context,
            )
            return response

        if not blocking:
            self._hass.async_create_task_internal(
                self._run_service_call_catch_exceptions(_remote_call(), service_call),
                f"remote service call {domain.lower()}.{service.lower()}",
                eager_start=True,
            )
            return None

        if return_response and not blocking:
            raise ServiceValidationError(
                translation_domain="homeassistant",
                translation_key="service_should_be_blocking",
                translation_placeholders={
                    "return_response": "return_response=True",
                    "non_blocking_argument": "blocking=False",
                },
            )

        result = await _remote_call()
        if not return_response:
            return None
        return result.get("response")


class RemoteHomeAssistant(CoreHomeAssistant):
    """Home Assistant subclass with remote websocket sync hooks."""

    def __init__(
        self,
        config_dir: str,
        *,
        remote_config: RemoteConfig | None = None,
    ) -> None:
        """Initialize a remote-capable Home Assistant instance."""
        super().__init__(config_dir)
        self.remote_config = remote_config or RemoteConfig.from_env()
        self.remote_api: HomeAssistantAPI | None = None
        self.remote_ready = False
        self._remote_state_ids: set[str] = set()
        self._remote_entity_registry_ids: set[str] = set()
        self._remote_unsubscribers: list[Callable[[], None]] = []

        if self.remote_config.enabled:
            self.remote_api = HomeAssistantAPI(
                websocket_url=self.remote_config.websocket_url,
                token=self.remote_config.token,
            )

        self.services = HybridServiceRegistry(self, self.remote_api)

    async def async_setup_remote(self) -> None:
        """Initialize remote sync."""
        if self.remote_ready or self.remote_api is None:
            return

        await self.remote_api.start(ssl=self.remote_config.ssl)

        if self.remote_config.sync_remote_services:
            await self.async_refresh_remote_services()

        if self.remote_config.sync_states:
            await self.async_refresh_remote_states()
            self._remote_unsubscribers.append(
                await self.remote_api.subscribe_events(
                    self._handle_remote_state_changed,
                    EVENT_STATE_CHANGED,
                )
            )
            self._remote_unsubscribers.append(
                await self.remote_api.subscribe_events(
                    self._handle_remote_state_reported,
                    EVENT_STATE_REPORTED,
                )
            )

        if self.remote_config.sync_entity_registry:
            await self.async_refresh_remote_entity_registry()
            self._remote_unsubscribers.append(
                await self.remote_api.subscribe_events(
                    self._handle_remote_entity_registry_event,
                    er.EVENT_ENTITY_REGISTRY_UPDATED,
                )
            )

        self._remote_unsubscribers.append(
            await self.remote_api.subscribe_events(
                self._handle_remote_service_registry_event,
                EVENT_SERVICE_REGISTERED,
            )
        )
        self._remote_unsubscribers.append(
            await self.remote_api.subscribe_events(
                self._handle_remote_service_registry_event,
                EVENT_SERVICE_REMOVED,
            )
        )

        self.remote_ready = True

    async def async_teardown_remote(self) -> None:
        """Stop remote sync."""
        while self._remote_unsubscribers:
            unsubscribe = self._remote_unsubscribers.pop()
            unsubscribe()

        if self.remote_api is not None:
            await self.remote_api.stop()

        self.remote_ready = False

    async def async_refresh_remote_services(self) -> None:
        """Refresh the cached remote services."""
        if self.remote_api is None:
            return
        services = await self.remote_api.async_get_services()
        self.services.async_set_remote_services(services)

    async def async_refresh_remote_states(self) -> None:
        """Fetch the remote state snapshot."""
        if self.remote_api is None:
            return
        states = await self.remote_api.async_get_states()
        self._apply_remote_state_snapshot(states)

    async def async_refresh_remote_entity_registry(self) -> None:
        """Fetch the remote entity registry snapshot."""
        if self.remote_api is None:
            return

        registry = er.async_get(self)
        entries = await self.remote_api.async_get_entity_registry()
        remote_ids: set[str] = set()

        for partial_entry in entries:
            entity_id = partial_entry["entity_id"].lower()
            try:
                full_entry = await self.remote_api.async_get_entity_registry_entry(entity_id)
            except FailedCommand:
                continue
            entry = self._build_registry_entry(full_entry)
            registry.entities[entry.entity_id] = entry
            remote_ids.add(entry.entity_id)

        for entity_id in self._remote_entity_registry_ids - remote_ids:
            registry.entities.pop(entity_id, None)

        registry._entities_data = registry.entities.data
        self._remote_entity_registry_ids = remote_ids

    @callback
    def _apply_remote_state_snapshot(self, states: list[dict[str, Any]]) -> None:
        """Apply a remote state snapshot without firing change events."""
        remote_ids: set[str] = set()
        state_store = self.states._states

        for state_payload in states:
            state = State.from_dict(state_payload)
            if state is None:
                continue
            entity_id = state.entity_id.lower()
            state_store[entity_id] = state
            remote_ids.add(entity_id)

        for entity_id in self._remote_state_ids - remote_ids:
            if entity_id in state_store:
                del state_store[entity_id]

        self._remote_state_ids = remote_ids

    async def _handle_remote_service_registry_event(
        self, message: dict[str, Any]
    ) -> None:
        """Refresh the service cache when the remote registry changes."""
        if not self.remote_config.sync_remote_services:
            return
        await self.async_refresh_remote_services()

    @callback
    def _handle_remote_state_changed(self, message: dict[str, Any]) -> None:
        """Apply a remote state_changed event locally."""
        event = message["event"]
        data = event["data"]
        entity_id = data["entity_id"].lower()
        context = _context_from_payload(event.get("context"))
        timestamp = _parse_datetime(event.get("time_fired")).timestamp()

        old_state = self.states.get(entity_id)
        if old_state is not None:
            old_state.expire()

        new_state_payload = data.get("new_state")
        if new_state_payload is None:
            self.states._states.pop(entity_id, None)
            self._remote_state_ids.discard(entity_id)
            self.bus.async_fire_internal(
                EVENT_STATE_CHANGED,
                {
                    "entity_id": entity_id,
                    "old_state": old_state,
                    "new_state": None,
                },
                origin=EventOrigin.remote,
                context=context,
                time_fired=timestamp,
            )
            return

        new_state = State.from_dict(new_state_payload)
        if new_state is None:
            return

        self.states._states[entity_id] = new_state
        self._remote_state_ids.add(entity_id)
        self.bus.async_fire_internal(
            EVENT_STATE_CHANGED,
            {
                "entity_id": entity_id,
                "old_state": old_state,
                "new_state": new_state,
            },
            origin=EventOrigin.remote,
            context=context,
            time_fired=timestamp,
        )

    @callback
    def _handle_remote_state_reported(self, message: dict[str, Any]) -> None:
        """Apply a remote state_reported event locally."""
        event = message["event"]
        data = event["data"]
        entity_id = data["entity_id"].lower()
        context = _context_from_payload(event.get("context"))
        state = self.states.get(entity_id)
        new_state_payload = data.get("new_state")
        if state is None or new_state_payload is None:
            return

        last_reported = _parse_datetime(data.get("last_reported"))
        old_last_reported = _parse_datetime(data.get("old_last_reported"))
        state.last_reported = last_reported
        state._cache["last_reported_timestamp"] = last_reported.timestamp()
        self.bus.async_fire_internal(
            EVENT_STATE_REPORTED,
            {
                "entity_id": entity_id,
                "last_reported": last_reported,
                "old_last_reported": old_last_reported,
                "new_state": state,
            },
            origin=EventOrigin.remote,
            context=context,
            time_fired=_parse_datetime(event.get("time_fired")).timestamp(),
        )

    async def _handle_remote_entity_registry_event(
        self, message: dict[str, Any]
    ) -> None:
        """Apply a remote entity_registry_updated event locally."""
        event = message["event"]
        data = dict(event["data"])
        context = _context_from_payload(event.get("context"))
        registry = er.async_get(self)
        action = data["action"]
        entity_id = data["entity_id"].lower()

        if action == "remove":
            registry.entities.pop(entity_id, None)
            registry._entities_data = registry.entities.data
            self._remote_entity_registry_ids.discard(entity_id)
        else:
            try:
                payload = await self.remote_api.async_get_entity_registry_entry(entity_id)  # type: ignore[union-attr]
            except (FailedCommand, NotConnected):
                if action == "create":
                    return
            else:
                entry = self._build_registry_entry(payload)
                old_entity_id = data.get("old_entity_id")
                if old_entity_id and old_entity_id in registry.entities:
                    registry.entities.pop(old_entity_id, None)
                    self._remote_entity_registry_ids.discard(old_entity_id)
                registry.entities[entry.entity_id] = entry
                registry._entities_data = registry.entities.data
                self._remote_entity_registry_ids.add(entry.entity_id)

        self.bus.async_fire_internal(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            data,
            origin=EventOrigin.remote,
            context=context,
            time_fired=_parse_datetime(event.get("time_fired")).timestamp(),
        )

    def _build_registry_entry(self, payload: Mapping[str, Any]) -> er.RegistryEntry:
        """Build a local entity registry entry from a websocket payload."""
        return er.RegistryEntry(
            aliases=set(payload.get("aliases", [])),
            area_id=payload.get("area_id"),
            categories=dict(payload.get("categories", {})),
            capabilities=payload.get("capabilities"),
            config_entry_id=payload.get("config_entry_id"),
            config_subentry_id=payload.get("config_subentry_id"),
            created_at=_parse_datetime(payload.get("created_at")),
            device_class=payload.get("device_class"),
            device_id=payload.get("device_id"),
            disabled_by=er.RegistryEntryDisabler(payload["disabled_by"])
            if payload.get("disabled_by")
            else None,
            entity_category=EntityCategory(payload["entity_category"])
            if payload.get("entity_category")
            else None,
            entity_id=payload["entity_id"].lower(),
            hidden_by=er.RegistryEntryHider(payload["hidden_by"])
            if payload.get("hidden_by")
            else None,
            icon=payload.get("icon"),
            id=payload["id"],
            has_entity_name=payload.get("has_entity_name", False),
            labels=set(payload.get("labels", [])),
            modified_at=_parse_datetime(payload.get("modified_at")),
            name=payload.get("name"),
            object_id_base=payload.get("original_name"),
            options=payload.get("options", {}),
            original_device_class=payload.get("original_device_class"),
            original_icon=payload.get("original_icon"),
            original_name=payload.get("original_name"),
            platform=payload["platform"],
            suggested_object_id=None,
            supported_features=0,
            translation_key=payload.get("translation_key"),
            unique_id=payload["unique_id"],
            previous_unique_id=None,
            unit_of_measurement=None,
        )
