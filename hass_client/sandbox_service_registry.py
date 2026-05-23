"""Service registry for sandbox mode.

Replaces HybridServiceRegistry. All service registrations are forwarded
to the host via sandbox/register_service. All service calls are forwarded
to the host via the standard call_service websocket command. When the host
forwards a call back (for sandbox-registered proxy services), it is
executed locally.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceRegistry,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceNotFound

from .api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


class SandboxServiceRegistry(ServiceRegistry):
    """Service registry that registers on host and forwards calls."""

    def __init__(self, hass: HomeAssistant, api: HomeAssistantAPI) -> None:
        """Initialize the sandbox service registry."""
        super().__init__(hass)
        self._api = api
        self._executing_forwarded = False

    @callback
    def async_register(
        self,
        domain: str,
        service: str,
        service_func: Any,
        schema: Any = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
        job_type: Any = None,
        **kwargs: Any,
    ) -> None:
        """Register service locally and schedule registration on host."""
        super().async_register(
            domain, service, service_func, schema,
            supports_response=supports_response,
            job_type=job_type,
            **kwargs,
        )
        self._hass.async_create_task(
            self._register_on_host(domain, service),
            f"sandbox_register_service_{domain}.{service}",
            eager_start=True,
        )

    async def _register_on_host(self, domain: str, service: str) -> None:
        """Register a service on the host."""
        if not self._api.connected:
            return
        try:
            await self._api.async_sandbox_register_service(domain, service)
            _LOGGER.debug("Registered %s.%s on host", domain, service)
        except Exception:
            _LOGGER.debug(
                "Failed to register %s.%s on host", domain, service,
                exc_info=True,
            )

    async def async_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        blocking: bool = False,
        context: Any = None,
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> ServiceResponse:
        """Forward service call to host."""
        if self._executing_forwarded:
            return await super().async_call(
                domain, service, service_data, blocking,
                context, target, return_response,
            )

        if not self._api.connected:
            return await super().async_call(
                domain, service, service_data, blocking,
                context, target, return_response,
            )

        serialized_data = _make_serializable(service_data) if service_data else None

        # Serialize context for forwarding to host
        context_data: dict[str, Any] | None = None
        if context is not None:
            context_data = {
                "id": context.id,
                "user_id": context.user_id,
                "parent_id": context.parent_id,
            }

        try:
            response = await self._api.async_call_service(
                domain=domain,
                service=service,
                service_data=serialized_data,
                target=target,
                return_response=return_response,
                context=context_data,
            )
        except Exception:
            if blocking or return_response:
                raise
            # Non-blocking calls silently swallow errors, matching standard
            # ServiceRegistry behavior where fire-and-forget calls log but
            # don't propagate exceptions to the caller.
            return None

        if not return_response:
            return None
        return response.get("response") if response else None

    async def async_execute_forwarded_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any],
        target: dict[str, Any] | None = None,
        return_response: bool = False,
        context_data: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a service call forwarded from the host."""
        from homeassistant.core import Context

        if not super().has_service(domain, service):
            raise ServiceNotFound(domain, service)

        # Reconstruct context from forwarded data
        context: Context | None = None
        if context_data:
            context = Context(
                id=context_data.get("id"),
                user_id=context_data.get("user_id"),
                parent_id=context_data.get("parent_id"),
            )

        self._executing_forwarded = True
        try:
            merged_data = dict(service_data)
            if target:
                merged_data.update(target)
            return await super().async_call(
                domain,
                service,
                merged_data,
                blocking=True,
                context=context,
                return_response=return_response,
            )
        finally:
            self._executing_forwarded = False


def _make_serializable(data: dict[str, Any]) -> dict[str, Any]:
    """Convert non-JSON-serializable values to strings."""
    result = {}
    for key, value in data.items():
        if isinstance(value, dt.datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dt.date):
            result[key] = value.isoformat()
        elif isinstance(value, dt.time):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = _make_serializable(value)
        elif isinstance(value, (list, tuple)):
            result[key] = [
                v.isoformat() if isinstance(v, (dt.datetime, dt.date, dt.time)) else v
                for v in value
            ]
        else:
            result[key] = value
    return result
