"""Tests for the sandbox-side ``sandbox/get_translations`` handler.

Covers :func:`hass_client.sandbox._collect_component_strings` (the loader that
mirrors core's translation read) and :meth:`SandboxRuntime._handle_get_translations`
(the channel handler that packs the result into a ``Struct``). The sandbox
holds the ``Integration`` for a custom domain — main does not — so this is
where the raw ``translations/<lang>.json`` and the ``title`` pre-fill come
from.
"""

import json
from pathlib import Path
import tempfile
from typing import Any

from hass_client._proto import sandbox_pb2 as pb
from hass_client.flow_runner import FlowRunner
from hass_client.sandbox import SandboxRuntime, _collect_component_strings
import pytest

from homeassistant import loader as ha_loader
from homeassistant.core import HomeAssistant


@pytest.fixture(name="hass")
async def _hass_fixture() -> HomeAssistant:
    """A sandbox-private bare HA, as the runtime builds via FlowRunner."""
    with tempfile.TemporaryDirectory(prefix="sandbox_translation_") as tmp:
        flow_runner = await FlowRunner.create(config_dir=tmp)
        try:
            yield flow_runner.hass
        finally:
            await flow_runner.async_stop()


def _install_custom_integration(
    hass: HomeAssistant, tmp_path: Path, *, domain: str, strings: dict[str, Any]
) -> ha_loader.Integration:
    """Stand up a custom integration on disk + in the loader cache.

    Writes ``<tmp_path>/<domain>/translations/en.json`` and injects a matching
    custom :class:`Integration` into ``DATA_INTEGRATIONS`` so
    ``async_get_integrations`` resolves it from cache.
    """
    root = tmp_path / domain
    (root / "translations").mkdir(parents=True)
    (root / "translations" / "en.json").write_text(json.dumps(strings))
    integration = ha_loader.Integration(
        hass,
        f"custom_components.{domain}",
        root,
        {
            "domain": domain,
            "name": "My Custom",
            "config_flow": True,
            "documentation": "https://example.com",
            "iot_class": "local_polling",
            "requirements": [],
            "dependencies": [],
            "codeowners": [],
        },
        {"translations"},
    )
    assert not integration.is_built_in
    assert integration.has_translations
    cache = hass.data.setdefault(ha_loader.DATA_INTEGRATIONS, {})
    cache[domain] = integration
    return integration


async def test_collect_strings_builtin_prefills_title(hass: HomeAssistant) -> None:
    """A built-in domain loads its bundled strings with a ``title``."""
    strings = await _collect_component_strings(hass, "en", ["counter"])

    assert "counter" in strings
    assert strings["counter"]
    # Built-in en.json already ships a title; it is preserved verbatim.
    assert strings["counter"]["title"] == "Counter"


async def test_collect_strings_custom_injects_title(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """A custom domain loads its on-disk strings; missing title ⇒ integration name."""
    _install_custom_integration(
        hass,
        tmp_path,
        domain="my_custom",
        # No "title" — the helper must inject integration.name. Main cannot
        # run this fallback (it holds no Integration for a custom domain).
        strings={
            "config": {"step": {"user": {"title": "Set up"}}},
            "entity": {"sensor": {"widget": {"name": "Widget"}}},
        },
    )

    strings = await _collect_component_strings(hass, "en", ["my_custom"])

    assert strings["my_custom"]["title"] == "My Custom"
    assert strings["my_custom"]["config"]["step"]["user"]["title"] == "Set up"
    assert strings["my_custom"]["entity"]["sensor"]["widget"]["name"] == "Widget"


async def test_collect_strings_empty_domains_returns_empty(
    hass: HomeAssistant,
) -> None:
    """No domains requested ⇒ no work, empty result."""
    assert await _collect_component_strings(hass, "en", []) == {}


async def test_handle_get_translations_packs_struct(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """The channel handler returns the raw dict packed into the result Struct."""
    _install_custom_integration(
        hass,
        tmp_path,
        domain="packed_custom",
        strings={"entity": {"sensor": {"w": {"name": "W"}}}},
    )
    runtime = SandboxRuntime(url="ws://x", group="custom")
    # The handler only reads ``flow_runner.hass``; wrap the fixture hass.
    runtime._flow_runner = FlowRunner(hass)  # noqa: SLF001

    result = await runtime._handle_get_translations(  # noqa: SLF001
        pb.GetTranslations(language="en", domains=["packed_custom"])
    )

    assert result.language == "en"
    packed = dict(result.strings)
    assert packed["packed_custom"]["title"] == "My Custom"
    assert packed["packed_custom"]["entity"]["sensor"]["w"]["name"] == "W"


async def test_handle_get_translations_without_flow_runner_is_empty() -> None:
    """No flow runner (channel never opened) ⇒ empty result, never raises."""
    runtime = SandboxRuntime(url="ws://x", group="custom")

    result = await runtime._handle_get_translations(  # noqa: SLF001
        pb.GetTranslations(language="en", domains=["whatever"])
    )

    assert result.language == "en"
    assert not dict(result.strings)
