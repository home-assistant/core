"""Entity bridge for sandbox integrations.

Intercepts entities created by integrations running in a sandbox,
registers them with the host HA instance, forwards state changes,
and dispatches method calls from the host back to local entities.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import EventOrigin, HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform

from .api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


class SandboxEntityBridge:
    """Bridges local entities to the host HA instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HomeAssistantAPI,
        sandbox_entry_id: str,
    ) -> None:
        """Initialize the entity bridge."""
        self.hass = hass
        self.api = api
        self.sandbox_entry_id = sandbox_entry_id
        self._local_entities: dict[str, Entity] = {}
        self._entity_id_to_host_id: dict[str, str] = {}
        self._host_id_to_entity_id: dict[str, str] = {}
        self._subscribed = False

    async def register_entities(self, platform: EntityPlatform) -> None:
        """Register all entities from a platform with the host."""
        for entity_id, entity in platform.entities.items():
            await self._register_entity(entity_id, entity, platform)

    async def _register_entity(
        self, entity_id: str, entity: Entity, platform: EntityPlatform
    ) -> None:
        """Register a single entity with the host."""
        kwargs: dict[str, Any] = {}

        if entity.unique_id:
            kwargs["unique_id"] = entity.unique_id
        else:
            kwargs["unique_id"] = entity_id

        if entity.name:
            kwargs["original_name"] = str(entity.name)
        if entity.icon:
            kwargs["original_icon"] = entity.icon
        if entity.supported_features:
            kwargs["supported_features"] = entity.supported_features
        if entity.entity_description and hasattr(entity.entity_description, "has_entity_name"):
            kwargs["has_entity_name"] = entity.entity_description.has_entity_name
        elif hasattr(entity, "_attr_has_entity_name"):
            kwargs["has_entity_name"] = entity._attr_has_entity_name

        capabilities = self._get_capabilities(entity)
        if capabilities:
            kwargs["capabilities"] = capabilities

        suggested_object_id = entity_id.split(".", 1)[1] if "." in entity_id else None
        if suggested_object_id:
            kwargs["suggested_object_id"] = suggested_object_id

        result = await self.api.async_sandbox_register_entity(
            sandbox_entry_id=self.sandbox_entry_id,
            domain=platform.domain,
            platform=platform.platform_name,
            **kwargs,
        )

        host_entity_id = result["entity_id"]
        self._local_entities[entity_id] = entity
        self._entity_id_to_host_id[entity_id] = host_entity_id
        self._host_id_to_entity_id[host_entity_id] = entity_id

        _LOGGER.info("Registered entity: %s -> %s", entity_id, host_entity_id)

        state = self.hass.states.get(entity_id)
        if state:
            await self.api.async_sandbox_update_state(
                host_entity_id,
                state.state,
                dict(state.attributes),
            )

    def _get_capabilities(self, entity: Entity) -> dict[str, Any]:
        """Extract capability attributes from an entity."""
        caps: dict[str, Any] = {}
        cap_attrs = entity.capability_attributes
        if cap_attrs:
            caps.update(cap_attrs)
        return caps

    @callback
    def start_state_forwarding(self) -> None:
        """Start forwarding local state changes to the host."""

        async def _on_state_changed(event: Any) -> None:
            if event.origin == EventOrigin.remote:
                return

            entity_id = event.data.get("entity_id", "")
            host_entity_id = self._entity_id_to_host_id.get(entity_id)
            if host_entity_id is None:
                return

            new_state = event.data.get("new_state")
            if new_state is None:
                return

            try:
                await self.api.async_sandbox_update_state(
                    host_entity_id,
                    new_state.state,
                    dict(new_state.attributes),
                )
            except Exception:
                _LOGGER.exception("Failed to push state for %s", host_entity_id)

        self.hass.bus.async_listen(EVENT_STATE_CHANGED, _on_state_changed)

    async def subscribe_entity_commands(self) -> None:
        """Subscribe to entity method calls and service calls from the host."""
        if self._subscribed:
            return
        self._subscribed = True

        async def _on_command(message: dict[str, Any]) -> None:
            event_data = message.get("event", {})
            cmd_type = event_data.get("type")

            if cmd_type == "call_method":
                await self._handle_entity_command(event_data)
            elif cmd_type == "call_service":
                await self._handle_service_call(event_data)

        await self.api.subscribe(
            _on_command,
            "sandbox/subscribe_entity_commands",
        )
        _LOGGER.info("Subscribed to commands from host")

    async def _handle_entity_command(self, event_data: dict[str, Any]) -> None:
        """Handle an entity method call from the host."""
        call_id = event_data.get("call_id")
        host_entity_id = event_data.get("entity_id")
        method_name = event_data.get("method")
        kwargs = event_data.get("kwargs", {})

        local_entity_id = self._host_id_to_entity_id.get(host_entity_id, "")
        entity = self._local_entities.get(local_entity_id)

        if entity is None:
            _LOGGER.warning(
                "Entity command for unknown entity: %s", host_entity_id
            )
            await self.api.async_sandbox_entity_command_result(
                call_id=call_id,
                success=False,
                error=f"Entity {host_entity_id} not found in sandbox",
            )
            return

        try:
            method = getattr(entity, method_name, None)
            if method is None:
                raise AttributeError(
                    f"Entity {local_entity_id} has no method {method_name}"
                )

            result = await method(**kwargs)

            await self.api.async_sandbox_entity_command_result(
                call_id=call_id,
                success=True,
                result=result if _is_serializable(result) else None,
            )
        except Exception as err:
            _LOGGER.exception(
                "Error executing %s on %s", method_name, local_entity_id
            )
            await self.api.async_sandbox_entity_command_result(
                call_id=call_id,
                success=False,
                error=str(err),
            )

    async def _handle_service_call(self, event_data: dict[str, Any]) -> None:
        """Handle a service call forwarded from the host."""
        from .sandbox_service_registry import SandboxServiceRegistry

        call_id = event_data.get("call_id")
        domain = event_data.get("domain", "")
        service = event_data.get("service", "")
        service_data = event_data.get("service_data", {})
        target = event_data.get("target")
        return_response = event_data.get("return_response", False)
        context_data = event_data.get("context")

        services = self.hass.services
        if not isinstance(services, SandboxServiceRegistry):
            await self.api.async_sandbox_service_call_result(
                call_id=call_id,
                success=False,
                error="Service registry not in sandbox mode",
            )
            return

        try:
            result = await services.async_execute_forwarded_call(
                domain, service, service_data,
                target=target,
                return_response=return_response,
                context_data=context_data,
            )
            await self.api.async_sandbox_service_call_result(
                call_id=call_id,
                success=True,
                result=result if _is_serializable(result) else None,
            )
        except Exception as err:
            _LOGGER.debug(
                "Error executing forwarded service %s.%s: %s",
                domain, service, err,
            )
            kwargs: dict[str, Any] = {
                "call_id": call_id,
                "success": False,
                "error": str(err),
                "error_type": type(err).__name__,
            }
            if hasattr(err, "translation_domain") and err.translation_domain:
                kwargs["translation_domain"] = err.translation_domain
            if hasattr(err, "translation_key") and err.translation_key:
                kwargs["translation_key"] = err.translation_key
            if hasattr(err, "translation_placeholders") and err.translation_placeholders:
                kwargs["translation_placeholders"] = err.translation_placeholders
            await self.api.async_sandbox_service_call_result(**kwargs)


def _is_serializable(value: Any) -> bool:
    """Check if a value is JSON-serializable."""
    if value is None:
        return True
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_serializable(v) for v in value)
    if isinstance(value, dict):
        return all(
            isinstance(k, str) and _is_serializable(v)
            for k, v in value.items()
        )
    return False
