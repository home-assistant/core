"""Sandbox-side approved-domains gate."""

from collections.abc import Callable, Iterable
import contextlib
import logging

_LOGGER = logging.getLogger(__name__)

ApproveListener = Callable[[str], None]


class ApprovedDomains:
    """Mutable set of domains the sandbox runtime is allowed to own."""

    def __init__(self, initial: Iterable[str] | None = None) -> None:
        """Initialise the gate, optionally seeded with a starter set."""
        self._counts: dict[str, int] = {}
        self._listeners: list[ApproveListener] = []
        if initial is not None:
            for domain in initial:
                self.add(domain)

    def add_listener(self, listener: ApproveListener) -> None:
        """Subscribe ``listener`` to absent→present domain transitions."""
        self._listeners.append(listener)

    def remove_listener(self, listener: ApproveListener) -> None:
        """Drop a previously-added approve listener (no-op if absent)."""
        with contextlib.suppress(ValueError):
            self._listeners.remove(listener)

    def add(self, domain: str) -> None:
        """Approve ``domain``; multiple ``add`` calls bump a refcount."""
        key = domain.lower()
        is_new = key not in self._counts
        self._counts[key] = self._counts.get(key, 0) + 1
        if is_new:
            for listener in self._listeners:
                listener(key)

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
        """Return whether ``event_type`` matches ``<approved_domain>_*``."""
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
