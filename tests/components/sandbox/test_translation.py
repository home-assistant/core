"""Tests for the main-side sandbox translation provider.

The provider resolves a sandboxed integration's group, batches its custom
domains into one ``sandbox/get_translations`` RPC per language, and returns the
raw strings for core's translation cache to overlay. Built-in domains are
carved out (main reads its own disk) and any channel failure degrades to empty
so the frontend translation path never blocks.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.sandbox import SandboxData
from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.channel import Channel
from homeassistant.components.sandbox.protocol import MSG_GET_TRANSLATIONS
from homeassistant.components.sandbox.proxy_flow import SandboxFlowProxy
from homeassistant.components.sandbox.router import SandboxFlowRouter
from homeassistant.components.sandbox.translation import SandboxTranslationProvider
from homeassistant.core import HomeAssistant

from ._helpers import FakeSandboxManager, make_channel_pair

from tests.common import MockConfigEntry, MockModule, mock_integration

_CUSTOM_STRINGS: dict[str, Any] = {
    "title": "My Custom",
    "config": {"step": {"user": {"title": "Set up"}}},
    "entity": {"sensor": {"widget": {"name": "Widget"}}},
    "state": {"_": {"on": "On"}},
    "services": {"do_it": {"name": "Do it"}},
    "exceptions": {"boom": {"message": "Boom"}},
}


def _serving_channel(
    hass: HomeAssistant, payload: dict[str, dict[str, Any]]
) -> tuple[Channel, Channel]:
    """A live channel pair whose sandbox end answers get_translations."""
    main, sandbox = make_channel_pair()

    async def _handler(msg: pb.GetTranslations) -> pb.GetTranslationsResult:
        result = pb.GetTranslationsResult(language=msg.language)
        result.strings.update(
            {domain: payload[domain] for domain in msg.domains if domain in payload}
        )
        return result

    sandbox.register(MSG_GET_TRANSLATIONS, _handler)
    main.start()
    sandbox.start()
    return main, sandbox


def _forging_channel(
    hass: HomeAssistant, extra: dict[str, dict[str, Any]]
) -> tuple[Channel, Channel]:
    """A channel whose sandbox end injects ``extra`` domains it wasn't asked for.

    Stands in for a compromised sandbox: it returns strings for every
    requested domain *plus* the foreign ``extra`` domains, attempting to
    poison a co-resident integration's frontend strings.
    """
    main, sandbox = make_channel_pair()

    async def _handler(msg: pb.GetTranslations) -> pb.GetTranslationsResult:
        result = pb.GetTranslationsResult(language=msg.language)
        for domain in msg.domains:
            result.strings.update({domain: _CUSTOM_STRINGS})
        result.strings.update(extra)
        return result

    sandbox.register(MSG_GET_TRANSLATIONS, _handler)
    main.start()
    sandbox.start()
    return main, sandbox


def _provider_with_bridge(
    hass: HomeAssistant, *, group: str, channel: Channel | None
) -> SandboxTranslationProvider:
    """Build a provider whose ``group`` bridge exposes ``channel``."""
    data = SandboxData()
    if channel is not None:
        data.bridges[group] = SimpleNamespace(channel=channel)  # type: ignore[assignment]
    return SandboxTranslationProvider(hass, data)


async def test_custom_entry_pulls_strings_over_rpc(hass: HomeAssistant) -> None:
    """A loaded custom sandboxed entry resolves its strings over the channel."""
    mock_integration(hass, MockModule("my_custom"), built_in=False)
    MockConfigEntry(domain="my_custom", sandbox="custom").add_to_hass(hass)
    main, sandbox = _serving_channel(hass, {"my_custom": _CUSTOM_STRINGS})
    provider = _provider_with_bridge(hass, group="custom", channel=main)

    try:
        result = await provider.async_get_translations(["en"], {"my_custom"})
    finally:
        await main.close()
        await sandbox.close()

    # Every frontend category round-trips, title pre-filled sandbox-side.
    assert result == {"en": {"my_custom": _CUSTOM_STRINGS}}


async def test_builtin_carveout_returns_nothing(hass: HomeAssistant) -> None:
    """A sandboxed built-in is served from main's disk — never over RPC."""
    mock_integration(hass, MockModule("my_builtin"), built_in=True)
    MockConfigEntry(domain="my_builtin", sandbox="built-in").add_to_hass(hass)
    main, sandbox = _serving_channel(hass, {"my_builtin": _CUSTOM_STRINGS})
    provider = _provider_with_bridge(hass, group="built-in", channel=main)

    try:
        result = await provider.async_get_translations(["en"], {"my_builtin"})
    finally:
        await main.close()
        await sandbox.close()

    assert result == {}


async def test_dead_channel_degrades_to_empty(hass: HomeAssistant) -> None:
    """A sandboxed custom whose group has no live channel yields no strings."""
    mock_integration(hass, MockModule("my_custom"), built_in=False)
    MockConfigEntry(domain="my_custom", sandbox="custom").add_to_hass(hass)
    # No bridge registered for the group ⇒ no channel.
    provider = _provider_with_bridge(hass, group="custom", channel=None)

    result = await provider.async_get_translations(["en"], {"my_custom"})

    assert result == {}


async def test_non_sandboxed_domain_skipped(hass: HomeAssistant) -> None:
    """A non-sandboxed entry (and an unknown domain) are left to the disk path."""
    mock_integration(hass, MockModule("plain"), built_in=False)
    MockConfigEntry(domain="plain").add_to_hass(hass)  # sandbox is None
    main, sandbox = _serving_channel(hass, {"plain": _CUSTOM_STRINGS})
    provider = _provider_with_bridge(hass, group="custom", channel=main)

    try:
        result = await provider.async_get_translations(["en"], {"plain", "nonexistent"})
    finally:
        await main.close()
        await sandbox.close()

    assert result == {}


async def test_flow_in_progress_resolves_group(hass: HomeAssistant) -> None:
    """A brand-new custom (no entry) resolves its group via the live flow."""
    main, sandbox = _serving_channel(hass, {"new_custom": _CUSTOM_STRINGS})
    proxy = SandboxFlowProxy(
        sandbox_group="custom",
        manager=FakeSandboxManager(),  # type: ignore[arg-type]
        handler_key="new_custom",
    )
    proxy.handler = "new_custom"
    flow_manager = hass.config_entries.flow
    flow_manager._handler_progress_index["new_custom"].add(proxy)
    provider = _provider_with_bridge(hass, group="custom", channel=main)

    try:
        # No code on main for a brand-new custom ⇒ IntegrationNotFound ⇒ RPC.
        result = await provider.async_get_translations(["en"], {"new_custom"})
    finally:
        flow_manager._handler_progress_index["new_custom"].discard(proxy)
        await main.close()
        await sandbox.close()

    assert result == {"en": {"new_custom": _CUSTOM_STRINGS}}


async def test_multiple_languages_batch_per_language(hass: HomeAssistant) -> None:
    """Each requested language gets its own RPC; results key by language."""
    mock_integration(hass, MockModule("my_custom"), built_in=False)
    MockConfigEntry(domain="my_custom", sandbox="custom").add_to_hass(hass)
    main, sandbox = _serving_channel(hass, {"my_custom": _CUSTOM_STRINGS})
    provider = _provider_with_bridge(hass, group="custom", channel=main)

    try:
        result = await provider.async_get_translations(["en", "de"], {"my_custom"})
    finally:
        await main.close()
        await sandbox.close()

    assert result == {
        "en": {"my_custom": _CUSTOM_STRINGS},
        "de": {"my_custom": _CUSTOM_STRINGS},
    }


async def test_unload_entry_invalidates_translations(hass: HomeAssistant) -> None:
    """Reloading/unloading a sandboxed entry evicts its cached strings."""
    manager = FakeSandboxManager()
    router = SandboxFlowRouter(hass, manager, data=SandboxData())  # type: ignore[arg-type]
    entry = MockConfigEntry(domain="my_custom", sandbox="custom")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sandbox.router.async_invalidate_translations"
    ) as invalidate:
        # No live sandbox for the group ⇒ unload returns True after invalidating.
        result = await router.async_unload_entry(entry)

    assert result is True
    invalidate.assert_called_once_with(hass, {"my_custom"})


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unload_plain_entry_does_not_invalidate(hass: HomeAssistant) -> None:
    """A non-sandboxed entry unload falls through without touching translations."""
    manager = FakeSandboxManager()
    router = SandboxFlowRouter(hass, manager, data=SandboxData())  # type: ignore[arg-type]
    entry = MockConfigEntry(domain="plain")  # sandbox is None
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sandbox.router.async_invalidate_translations"
    ) as invalidate:
        result = await router.async_unload_entry(entry)

    assert result is None
    invalidate.assert_not_called()


async def test_foreign_returned_domain_is_dropped(hass: HomeAssistant) -> None:
    """Strings for a domain the group wasn't asked to resolve are discarded."""
    mock_integration(hass, MockModule("my_custom"), built_in=False)
    MockConfigEntry(domain="my_custom", sandbox="custom").add_to_hass(hass)
    # The sandbox forges a "hue" entry alongside its own "my_custom".
    main, sandbox = _forging_channel(hass, {"hue": {"title": "PWNED"}})
    provider = _provider_with_bridge(hass, group="custom", channel=main)

    try:
        result = await provider.async_get_translations(["en"], {"my_custom"})
    finally:
        await main.close()
        await sandbox.close()

    # Only the requested ∩ returned domain survives; the foreign "hue" is gone.
    assert result == {"en": {"my_custom": _CUSTOM_STRINGS}}
    assert "hue" not in result.get("en", {})
