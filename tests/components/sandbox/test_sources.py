"""Tests for the main-side integration-source resolver registry."""

import pytest

from homeassistant.components.sandbox.sources import (
    IntegrationSourceDict,
    SandboxSourceError,
    async_register_sandbox_source_resolver,
    async_resolve_integration_source,
)
from homeassistant.core import HomeAssistant

from tests.common import MockModule, mock_integration


async def test_resolve_builtin_returns_builtin_kind(hass: HomeAssistant) -> None:
    """A built-in integration short-circuits to ``{kind: builtin}``."""
    mock_integration(hass, MockModule("demo_builtin"))

    source = await async_resolve_integration_source(hass, "demo_builtin")

    assert source.kind == "builtin"
    assert source.url == ""


async def test_resolve_builtin_ignores_resolvers(hass: HomeAssistant) -> None:
    """Built-ins never consult a resolver, even when one is registered."""

    def _resolver(domain: str) -> IntegrationSourceDict | None:
        raise AssertionError("resolver must not be consulted for built-ins")

    async_register_sandbox_source_resolver(hass, _resolver)
    mock_integration(hass, MockModule("demo_builtin2"))

    source = await async_resolve_integration_source(hass, "demo_builtin2")

    assert source.kind == "builtin"


async def test_resolve_custom_uses_registered_resolver(hass: HomeAssistant) -> None:
    """A custom integration resolves to the registered git source."""
    mock_integration(hass, MockModule("my_custom"), built_in=False)

    def _resolver(domain: str) -> IntegrationSourceDict | None:
        assert domain == "my_custom"
        return {
            "kind": "git",
            "url": "https://github.com/owner/my_custom",
            "ref": "a" * 40,
            "tag": "v1.2.3",
        }

    async_register_sandbox_source_resolver(hass, _resolver)

    source = await async_resolve_integration_source(hass, "my_custom")

    assert source.kind == "git"
    assert source.url == "https://github.com/owner/my_custom"
    assert source.ref == "a" * 40
    assert source.tag == "v1.2.3"
    assert source.domain == "my_custom"
    # subdir defaults from the domain when the resolver omits it.
    assert source.subdir == "custom_components/my_custom"


async def test_resolve_custom_without_resolver_raises(hass: HomeAssistant) -> None:
    """A custom integration with no resolver cannot run — surface it."""
    mock_integration(hass, MockModule("orphan_custom"), built_in=False)

    with pytest.raises(SandboxSourceError, match="no sandbox source resolver"):
        await async_resolve_integration_source(hass, "orphan_custom")


async def test_resolve_custom_resolver_returning_none_raises(
    hass: HomeAssistant,
) -> None:
    """A resolver that doesn't know the domain falls through to the error."""
    mock_integration(hass, MockModule("unknown_custom"), built_in=False)
    async_register_sandbox_source_resolver(hass, lambda domain: None)

    with pytest.raises(SandboxSourceError, match="no sandbox source resolver"):
        await async_resolve_integration_source(hass, "unknown_custom")


async def test_resolve_git_source_without_ref_raises(hass: HomeAssistant) -> None:
    """A git source missing its pinned sha is rejected (no moving tags)."""
    mock_integration(hass, MockModule("unpinned_custom"), built_in=False)
    async_register_sandbox_source_resolver(
        hass,
        lambda domain: {
            "kind": "git",
            "url": "https://github.com/owner/unpinned_custom",
            "tag": "v1.0.0",
        },
    )

    with pytest.raises(SandboxSourceError, match="must pin"):
        await async_resolve_integration_source(hass, "unpinned_custom")


async def test_resolvers_consulted_in_order(hass: HomeAssistant) -> None:
    """The first resolver returning a source wins."""
    mock_integration(hass, MockModule("ordered_custom"), built_in=False)
    async_register_sandbox_source_resolver(hass, lambda domain: None)
    async_register_sandbox_source_resolver(
        hass,
        lambda domain: {
            "kind": "git",
            "url": "https://github.com/owner/ordered_custom",
            "ref": "b" * 40,
        },
    )

    source = await async_resolve_integration_source(hass, "ordered_custom")

    assert source.ref == "b" * 40


async def test_unregister_resolver(hass: HomeAssistant) -> None:
    """Unregistering a resolver removes it from the consulted set."""
    mock_integration(hass, MockModule("gone_custom"), built_in=False)
    unregister = async_register_sandbox_source_resolver(
        hass,
        lambda domain: {
            "kind": "git",
            "url": "https://github.com/owner/gone_custom",
            "ref": "c" * 40,
        },
    )

    unregister()

    with pytest.raises(SandboxSourceError):
        await async_resolve_integration_source(hass, "gone_custom")
