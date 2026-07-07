"""Main-side translation provider for sandboxed integrations.

A custom integration runs in an isolated sandbox process; its code — and so
its ``translations/<lang>.json`` — is never on main's disk. Main's translation
cache therefore resolves the domain to ``IntegrationNotFound`` and serves no
strings (entity names, config-flow labels, services, exceptions all vanish).

This module fills that gap. It registers a provider into core's
sandbox-agnostic translation hook
(:func:`homeassistant.helpers.translation.async_register_sandbox_translation_provider`).
For each requested component the provider resolves the owning sandbox group,
batches that group's custom domains into one ``sandbox/get_translations`` RPC
per language, and hands the raw (``title``-pre-filled) strings back to the
cache, which merges them as if they came off disk.

Two invariants keep it safe:

* **Built-in carve-out.** A sandboxed built-in integration's manifest +
  translations resolve on main from the bundled package, byte-identical to the
  sandbox's. Those never cross the wire — the provider returns nothing for
  ``Integration.is_built_in`` domains and main reads its own disk.
* **Degrade to empty.** The overlay runs under the translation cache lock, so
  it must never block the frontend. A group with no live channel — or an RPC
  that fails or times out — yields no strings for those domains (they fall
  through to main's empty disk result), never an exception.
"""

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import IntegrationNotFound, async_get_integration

from ._proto import sandbox_pb2 as pb
from .channel import Channel, ChannelClosedError, ChannelRemoteError
from .messages import MSG_GET_TRANSLATIONS, decode_json_dict
from .proxy_flow import SandboxFlowProxy

if TYPE_CHECKING:
    from . import SandboxData

_LOGGER = logging.getLogger(__name__)

# The overlay runs under the translation cache lock; cap the round-trip so a
# wedged (but not closed) sandbox channel cannot hang the frontend translation
# endpoint. A timeout degrades to empty, exactly like a dead channel.
_RPC_TIMEOUT = 5.0


class SandboxTranslationProvider:
    """Resolve sandboxed integrations' translation strings over the channel."""

    def __init__(self, hass: HomeAssistant, data: SandboxData) -> None:
        """Bind the provider to the running sandbox data."""
        self._hass = hass
        self._data = data

    async def async_get_translations(
        self, languages: list[str], components: set[str]
    ) -> dict[str, dict[str, Any]]:
        """Return ``{language: {domain: raw_strings}}`` for owned domains.

        Only custom domains that are sandboxed into a group with a live
        channel produce strings; everything else is omitted so it keeps its
        on-disk (or empty) result. Never raises — see the module docstring.
        """
        domains_by_group: dict[str, set[str]] = {}
        for domain in components:
            group = await self._resolve_sandbox_group(domain)
            if group is not None:
                domains_by_group.setdefault(group, set()).add(domain)

        if not domains_by_group:
            return {}

        result: dict[str, dict[str, Any]] = {}
        for group, domains in domains_by_group.items():
            bridge = self._data.bridges.get(group)
            channel = bridge.channel if bridge is not None else None
            if channel is None:
                # Sandbox not up / channel down — degrade to empty.
                continue
            for language in languages:
                strings = await self._fetch(channel, group, language, domains)
                # Trust only the domains we actually asked this group to
                # resolve. A compromised sandbox can return strings for any
                # domain (e.g. a co-requested ``hue`` / ``http`` it does not
                # own) to poison a victim integration's frontend strings; keep
                # only the requested ∩ returned intersection.
                for domain in domains & strings.keys():
                    result.setdefault(language, {})[domain] = strings[domain]
        return result

    async def _resolve_sandbox_group(self, domain: str) -> str | None:
        """Return the sandbox group owning ``domain``, or ``None``.

        ``None`` means "leave it to the disk path": the domain is not
        sandboxed, or it is a built-in whose files main already holds.
        Resolution order matches the flow router — a loaded entry's
        ``sandbox`` field wins; otherwise an in-progress sandbox flow's group
        (for a brand-new custom with no entry yet).
        """
        group: str | None = None
        for entry in self._hass.config_entries.async_entries(domain):
            if entry.sandbox is not None:
                group = entry.sandbox
                break
        if group is None:
            group = self._group_for_flow_in_progress(domain)
        if group is None:
            return None

        # Built-in carve-out: main reads its byte-identical bundled files.
        try:
            integration = await async_get_integration(self._hass, domain)
        except IntegrationNotFound:
            # No code on main ⇒ a custom that genuinely needs the RPC.
            return group
        if integration.is_built_in:
            return None
        return group

    @callback
    def _group_for_flow_in_progress(self, domain: str) -> str | None:
        """Return the group of an in-progress sandbox flow for ``domain``.

        A brand-new custom integration being added has no ``ConfigEntry`` yet,
        so its group lives only on the live :class:`SandboxFlowProxy` driving
        the add-integration dialog. The public flow API exposes only
        serialized results, so the live flow object is reached through the flow
        manager's per-handler progress index.
        """
        index = self._hass.config_entries.flow._handler_progress_index  # noqa: SLF001
        for flow in index.get(domain, ()):
            if isinstance(flow, SandboxFlowProxy):
                return flow.sandbox_group
        return None

    async def _fetch(
        self, channel: Channel, group: str, language: str, domains: set[str]
    ) -> dict[str, Any]:
        """Issue one batched ``get_translations`` RPC; empty on any failure."""
        request = pb.GetTranslations(language=language, domains=sorted(domains))
        try:
            result = await channel.call(
                MSG_GET_TRANSLATIONS, request, timeout=_RPC_TIMEOUT
            )
        except (ChannelClosedError, ChannelRemoteError, TimeoutError) as err:
            _LOGGER.debug(
                "sandbox[%s]: get_translations(%s) failed (%s); serving empty",
                group,
                language,
                err,
            )
            return {}
        return decode_json_dict(result.strings)
