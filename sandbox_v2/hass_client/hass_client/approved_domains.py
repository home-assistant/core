"""Sandbox-side approved-domains gate (Phase 6).

A single shared :class:`ApprovedDomains` instance tracks which domains
the sandbox is allowed to own. It is the firewall the user asked for:
the service mirror and event mirror consult it before pushing anything
up to main, so a sandboxed integration can't silently impersonate (say)
``notify`` or fire ``persistent_notification_event`` on main's bus.

Population:

* The :class:`hass_client.entry_runner.EntryRunner` adds an entry's
  domain when ``sandbox_v2/entry_setup`` succeeds, and removes it on
  ``entry_unload`` once the last entry for that domain unloads.
* The :class:`hass_client.entity_bridge.EntityBridge` adds the entity's
  domain on each successful ``register_entity``. This covers the
  ``light`` is approved because a sandboxed integration registers light
  entities clause from the plan.

Lookups:

* :meth:`approves` — exact domain match. Used by the service mirror.
* :meth:`approves_event` — ``<domain>_*`` pattern match against any
  approved domain. Used by the event mirror.

Domain comparison is case-insensitive; everything is normalised to
lowercase at insertion time so the lookups stay cheap.
"""

from collections.abc import Iterable
import logging

_LOGGER = logging.getLogger(__name__)


class ApprovedDomains:
    """Mutable set of domains the sandbox runtime is allowed to own."""

    def __init__(self, initial: Iterable[str] | None = None) -> None:
        """Initialise the gate, optionally seeded with a starter set."""
        self._counts: dict[str, int] = {}
        if initial is not None:
            for domain in initial:
                self.add(domain)

    def add(self, domain: str) -> None:
        """Approve ``domain``; multiple ``add`` calls bump a refcount."""
        key = domain.lower()
        self._counts[key] = self._counts.get(key, 0) + 1

    def remove(self, domain: str) -> None:
        """Drop one ``add`` for ``domain``; harmless when over-removed."""
        key = domain.lower()
        count = self._counts.get(key, 0)
        if count <= 1:
            self._counts.pop(key, None)
            return
        self._counts[key] = count - 1

    def approves(self, domain: str) -> bool:
        """Return whether ``domain`` is in the approved set."""
        return domain.lower() in self._counts

    def approves_event(self, event_type: str) -> bool:
        """Return whether ``event_type`` matches ``<approved_domain>_*``.

        Event names like ``zha_event`` and ``mqtt_message_received`` are
        matched by the longest approved-domain prefix followed by ``_``;
        this means a sandbox owning ``device_tracker`` correctly
        approves ``device_tracker_see`` (which a shorter prefix would
        miss).
        """
        if "_" not in event_type:
            return False
        lower = event_type.lower()
        return any(lower.startswith(f"{domain}_") for domain in self._counts)

    @property
    def domains(self) -> frozenset[str]:
        """Snapshot of the current approved-domain set."""
        return frozenset(self._counts)

    def __contains__(self, domain: object) -> bool:
        """Allow ``"light" in approved`` style membership tests."""
        if not isinstance(domain, str):
            return False
        return self.approves(domain)


__all__ = ["ApprovedDomains"]
