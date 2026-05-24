"""Sandbox-side entry runner — loads integrations + drives ``async_setup_entry``.

The manager pushes a serialised :class:`ConfigEntry` via
``sandbox_v2/entry_setup`` (see :mod:`hass_client.protocol`). The runner
rebuilds the entry on the sandbox's private :class:`HomeAssistant`,
calls ``hass.config_entries.async_setup`` to load the owning integration,
and reports back. Main holds the canonical entry; the sandbox copy is
ephemeral state used by the integration's lifecycle hooks.
"""

from collections.abc import Mapping
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .approved_domains import ApprovedDomains
from .channel import Channel
from .protocol import MSG_CALL_SERVICE, MSG_ENTRY_SETUP, MSG_ENTRY_UNLOAD

_LOGGER = logging.getLogger(__name__)


class EntryRunner:
    """Load integrations on demand and run config entries inside the sandbox."""

    def __init__(
        self, hass: HomeAssistant, approved: ApprovedDomains | None = None
    ) -> None:
        """Initialise with the sandbox-private HA instance.

        ``approved`` is shared with the service + event mirrors so an
        entry's domain becomes approved as soon as setup completes.
        """
        self.hass = hass
        self.approved = approved if approved is not None else ApprovedDomains()

    def register(self, channel: Channel) -> None:
        """Wire the ``sandbox_v2/entry_*`` + ``call_service`` handlers."""
        channel.register(MSG_ENTRY_SETUP, self._handle_entry_setup)
        channel.register(MSG_ENTRY_UNLOAD, self._handle_entry_unload)
        channel.register(MSG_CALL_SERVICE, self._handle_call_service)

    async def _handle_entry_setup(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Build a :class:`ConfigEntry`, register it, and call async_setup."""
        try:
            entry = _entry_from_payload(payload)
        except (KeyError, TypeError) as err:
            return {"ok": False, "reason": f"bad payload: {err}"}

        config_entries = self.hass.config_entries
        if config_entries.async_get_entry(entry.entry_id) is not None:
            return {"ok": False, "reason": "entry already loaded"}

        # ConfigEntries doesn't expose a "add without persist" hook; the
        # sandbox's instance has no Store backing, so we drop the entry
        # straight into the internal map. `async_setup` then finds it via
        # `async_get_known_entry`.
        config_entries._entries[entry.entry_id] = entry  # noqa: SLF001
        try:
            ok = await config_entries.async_setup(entry.entry_id)
        except Exception as err:
            _LOGGER.exception(
                "sandbox entry_setup raised for %s (%s)", entry.title, entry.domain
            )
            return {"ok": False, "reason": str(err) or err.__class__.__name__}
        if not ok:
            return {
                "ok": False,
                "reason": entry.reason or f"async_setup returned {ok!r}",
            }
        self.approved.add(entry.domain)
        return {"ok": True}

    async def _handle_entry_unload(
        self, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Unload an entry by id and drop it from the sandbox's store."""
        entry_id = payload["entry_id"]
        config_entries = self.hass.config_entries
        entry = config_entries.async_get_entry(entry_id)
        if entry is None:
            return {"ok": True}
        try:
            unloaded = await config_entries.async_unload(entry_id)
        except Exception as err:
            _LOGGER.exception("sandbox entry_unload raised for %s", entry_id)
            return {"ok": False, "reason": str(err) or err.__class__.__name__}
        config_entries._entries.pop(entry_id, None)  # noqa: SLF001
        # Drop one approval refcount; another loaded entry of the same
        # domain keeps it approved.
        self.approved.remove(entry.domain)
        return {"ok": bool(unloaded)}

    async def _handle_call_service(
        self, payload: Mapping[str, Any]
    ) -> Any:
        """Dispatch a main→sandbox service call through HA's normal path.

        Service-handler errors propagate as raised exceptions so the
        :class:`Channel`'s error frame carries the type name (e.g.
        ``Invalid``). Main maps those back to ``TypeError`` /
        ``HomeAssistantError`` in :mod:`bridge`'s exception translator.
        """
        domain = payload["domain"]
        service = payload["service"]
        target = payload.get("target") or {}
        service_data = dict(payload.get("service_data") or {})
        return_response = bool(payload.get("return_response", False))
        if return_response:
            result = await self.hass.services.async_call(
                domain,
                service,
                service_data,
                blocking=True,
                target=target,
                return_response=True,
            )
            return {"response": result}
        await self.hass.services.async_call(
            domain,
            service,
            service_data,
            blocking=True,
            target=target,
        )
        return None


def _entry_from_payload(payload: Mapping[str, Any]) -> ConfigEntry:
    """Rebuild a :class:`ConfigEntry` from the wire payload.

    Only fields the integration's setup hooks need are surfaced — the
    sandbox does not persist entries or track update listeners.
    """
    return ConfigEntry(
        version=int(payload["version"]),
        minor_version=int(payload.get("minor_version", 1)),
        domain=payload["domain"],
        title=payload.get("title", ""),
        data=MappingProxyType(dict(payload.get("data") or {})),
        options=MappingProxyType(dict(payload.get("options") or {})),
        source=payload.get("source", "user"),
        unique_id=payload.get("unique_id"),
        entry_id=payload["entry_id"],
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
        state=ConfigEntryState.NOT_LOADED,
    )


__all__ = ["EntryRunner"]
