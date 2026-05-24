"""Sandbox-side service-registration mirror (Phase 6).

Watches ``EVENT_SERVICE_REGISTERED`` / ``EVENT_SERVICE_REMOVED`` on the
sandbox bus. For each registration whose domain is in
:class:`ApprovedDomains`, it pushes ``sandbox_v2/register_service`` to
main with the metadata main needs to install a forwarding handler. Same
shape for removals via ``sandbox_v2/unregister_service``.

Schemas are intentionally not serialised in Phase 6 — the sandbox is the
authoritative validator (the call comes back over
``sandbox_v2/call_service`` and is run through ``services.async_call``
on the sandbox side, where the real schema lives). Main only needs
``supports_response`` so it can register the proxy with the right return
shape; the proxy handler forwards everything else verbatim.
"""

import asyncio
import logging
from typing import Any

from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_SERVICE,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.core import Event, HomeAssistant, callback

from .approved_domains import ApprovedDomains
from .channel import Channel
from .protocol import MSG_REGISTER_SERVICE, MSG_UNREGISTER_SERVICE
from .schema_bridge import serialize_schema

_LOGGER = logging.getLogger(__name__)


class ServiceMirror:
    """Forward sandbox-side service registrations up to main.

    One instance per sandbox process. Lifetime is bound to the
    :class:`Channel` it was registered against: :meth:`register` attaches
    the bus listeners, :meth:`async_stop` detaches them.
    """

    def __init__(self, hass: HomeAssistant, approved: ApprovedDomains) -> None:
        """Initialise with the sandbox HA and the shared approved-domains gate."""
        self.hass = hass
        self.approved = approved
        self._channel: Channel | None = None
        self._unsub_registered: Any = None
        self._unsub_removed: Any = None
        # Track what we've pushed so we don't double-register on the
        # main side if EVENT_SERVICE_REGISTERED fires twice for the same
        # (domain, service).
        self._mirrored: set[tuple[str, str]] = set()

    def register(self, channel: Channel) -> None:
        """Capture ``channel`` and start watching the service registry."""
        self._channel = channel
        self._unsub_registered = self.hass.bus.async_listen(
            EVENT_SERVICE_REGISTERED, self._on_service_registered
        )
        self._unsub_removed = self.hass.bus.async_listen(
            EVENT_SERVICE_REMOVED, self._on_service_removed
        )

    async def async_stop(self) -> None:
        """Detach the bus listeners."""
        if self._unsub_registered is not None:
            self._unsub_registered()
            self._unsub_registered = None
        if self._unsub_removed is not None:
            self._unsub_removed()
            self._unsub_removed = None

    @callback
    def _on_service_registered(self, event: Event) -> None:
        if self._channel is None or self._channel.closed:
            return
        domain = str(event.data[ATTR_DOMAIN])
        service = str(event.data[ATTR_SERVICE])
        if not self.approved.approves(domain):
            _LOGGER.warning(
                "ServiceMirror: refusing to mirror %s.%s — domain not approved"
                " for this sandbox (approved=%s)",
                domain,
                service,
                sorted(self.approved.domains),
            )
            return
        key = (domain.lower(), service.lower())
        if key in self._mirrored:
            return
        supports_response = _supports_response(self.hass, domain, service)
        payload: dict[str, Any] = {
            "domain": domain,
            "service": service,
            "supports_response": supports_response,
        }
        schema = _service_schema(self.hass, domain, service)
        if schema is not None:
            payload["schema"] = schema
        self._mirrored.add(key)
        asyncio.create_task(  # noqa: RUF006
            self._push_register(payload, key),
            name=f"sandbox_v2:register_service:{domain}.{service}",
        )

    @callback
    def _on_service_removed(self, event: Event) -> None:
        if self._channel is None or self._channel.closed:
            return
        domain = str(event.data[ATTR_DOMAIN])
        service = str(event.data[ATTR_SERVICE])
        key = (domain.lower(), service.lower())
        if key not in self._mirrored:
            return
        self._mirrored.discard(key)
        payload = {"domain": domain, "service": service}
        asyncio.create_task(  # noqa: RUF006
            self._push_unregister(payload),
            name=f"sandbox_v2:unregister_service:{domain}.{service}",
        )

    async def _push_register(
        self, payload: dict[str, Any], key: tuple[str, str]
    ) -> None:
        assert self._channel is not None
        try:
            await self._channel.call(MSG_REGISTER_SERVICE, payload)
        except Exception:
            _LOGGER.exception(
                "ServiceMirror: register failed for %s.%s",
                payload["domain"],
                payload["service"],
            )
            # Roll back the mirrored bookkeeping so a retry can succeed.
            self._mirrored.discard(key)

    async def _push_unregister(self, payload: dict[str, Any]) -> None:
        assert self._channel is not None
        try:
            await self._channel.call(MSG_UNREGISTER_SERVICE, payload)
        except Exception:
            _LOGGER.exception(
                "ServiceMirror: unregister failed for %s.%s",
                payload["domain"],
                payload["service"],
            )


def _service_schema(
    hass: HomeAssistant, domain: str, service: str
) -> list[dict[str, Any]] | None:
    """Serialise the registered service's voluptuous schema for the wire.

    Returns ``None`` when the service registers with no schema (very
    common), when the schema doesn't survive voluptuous_serialize, or
    when the lookup races and the service isn't visible yet — in every
    case main falls back to ``schema=None`` and the sandbox's own
    handler still validates.
    """
    services = hass.services.async_services_for_domain(domain)
    service_obj = services.get(service.lower())
    if service_obj is None:
        return None
    return serialize_schema(service_obj.schema)


def _supports_response(hass: HomeAssistant, domain: str, service: str) -> str:
    """Best-effort lookup of the service's ``supports_response`` value.

    Returns the lowercase string value (``"none"`` / ``"only"`` /
    ``"optional"``) since that's what main needs to pass back to
    :meth:`hass.services.async_register`. Falls back to ``"none"`` if
    the service isn't actually registered yet (a race with the
    ``EVENT_SERVICE_REGISTERED`` listener) — the lookup is best-effort
    and main treats the metadata as authoritative.
    """
    services = hass.services.async_services_for_domain(domain)
    service_obj = services.get(service.lower())
    if service_obj is None:
        return "none"
    value = getattr(service_obj.supports_response, "value", None)
    return str(value).lower() if value is not None else "none"


__all__ = ["ServiceMirror"]
