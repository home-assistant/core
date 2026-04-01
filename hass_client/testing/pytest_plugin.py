"""Pytest bridge for running Home Assistant core tests against hass-client."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from functools import cached_property
import json
from pathlib import Path
import re
import threading
from typing import Any
from unittest.mock import Mock

KEY_REFERENCE_RE = re.compile(r"\[%key:([a-z0-9_]+(?:::(?:[a-z0-9-_])+)+)%\]")


def _noop_timer() -> None:
    """Compatibility no-op callback for mocked loop timer handles."""


def _flatten_translations(
    translations: dict[str, Any],
    *,
    prefix: tuple[str, ...] = (),
) -> dict[str, str]:
    """Flatten nested translations into Lokalise reference keys."""
    flattened: dict[str, str] = {}
    for key, value in translations.items():
        new_prefix = (*prefix, key)
        if isinstance(value, dict):
            flattened.update(_flatten_translations(value, prefix=new_prefix))
        elif isinstance(value, str):
            flattened["::".join(new_prefix)] = value
    return flattened


def _substitute_translation_string(
    value: str,
    substitutions: dict[str, str],
    resolved: dict[str, str],
    stack: set[str],
) -> str | None:
    """Substitute Lokalise-style references in a translation string."""
    new_value = value
    for reference in KEY_REFERENCE_RE.findall(value):
        if reference in stack:
            return None
        if reference in resolved:
            replacement = resolved[reference]
        else:
            raw_replacement = substitutions.get(reference)
            if raw_replacement is None:
                return None
            replacement = _substitute_translation_string(
                raw_replacement,
                substitutions,
                resolved,
                stack | {reference},
            )
            if replacement is None:
                return None
            resolved[reference] = replacement
        new_value = new_value.replace(f"[%key:{reference}%]", replacement)
    return new_value


def _resolve_translations(
    translations: dict[str, Any],
    substitutions: dict[str, str],
    resolved: dict[str, str],
) -> dict[str, Any]:
    """Resolve Lokalise-style references in nested translation data."""
    result: dict[str, Any] = {}
    for key, value in translations.items():
        if isinstance(value, dict):
            nested = _resolve_translations(value, substitutions, resolved)
            if nested:
                result[key] = nested
            continue

        if not isinstance(value, str):
            continue

        substituted = _substitute_translation_string(value, substitutions, resolved, set())
        if substituted is not None:
            result[key] = substituted

    return result


def _merge_missing_translations(
    target: dict[str, Any],
    source: dict[str, Any],
) -> None:
    """Recursively merge missing translation keys into a target dict."""
    for key, value in source.items():
        if key not in target:
            target[key] = value
            continue

        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_missing_translations(existing, value)


class _StringsResolver:
    """Resolve Home Assistant strings.json content into translation payloads."""

    def __init__(self, package_root: Path) -> None:
        """Initialize the resolver."""
        self._package_root = package_root
        self._flattened_index: dict[str, str] | None = None
        self._component_cache: dict[str, dict[str, Any]] = {}
        self._resolved_references: dict[str, str] = {}

    def _load_json(self, path: Path) -> dict[str, Any]:
        """Load JSON from a path, returning an empty dict when absent."""
        if not path.is_file():
            return {}
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}

    def _build_flattened_index(self) -> dict[str, str]:
        """Build the flattened strings index across common and component strings."""
        flattened = _flatten_translations(self._load_json(self._package_root / "strings.json"))
        components_dir = self._package_root / "components"
        for strings_path in components_dir.glob("*/strings.json"):
            domain = strings_path.parent.name
            flattened.update(
                _flatten_translations(
                    {"component": {domain: self._load_json(strings_path)}}
                )
            )
        return flattened

    def resolve_component(self, domain: str) -> dict[str, Any]:
        """Resolve a component strings.json file into translation data."""
        if domain not in self._component_cache:
            strings_path = self._package_root / "components" / domain / "strings.json"
            component_strings = self._load_json(strings_path)
            if not component_strings:
                self._component_cache[domain] = {}
            else:
                if self._flattened_index is None:
                    self._flattened_index = self._build_flattened_index()
                self._component_cache[domain] = _resolve_translations(
                    component_strings,
                    self._flattened_index,
                    self._resolved_references,
                )
        return self._component_cache[domain]

    def get_exception_message(self, domain: str, key: str) -> str | None:
        """Return an exception message from strings.json when available."""
        message = (
            self.resolve_component(domain)
            .get("exceptions", {})
            .get(key, {})
            .get("message")
        )
        return message if isinstance(message, str) else None


def _build_exception_message_fallback(original, strings_resolver: _StringsResolver):
    """Build a fallback that reads strings.json when translations are not generated."""

    def async_get_exception_message(
        translation_domain: str,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> str:
        message = original(
            translation_domain,
            translation_key,
            translation_placeholders,
        )
        if message != translation_key:
            return message

        component_message = strings_resolver.get_exception_message(
            translation_domain, translation_key
        )
        if not component_message:
            return message

        component_message = component_message.rstrip(".")
        if not translation_placeholders:
            return component_message

        try:
            return component_message.format(**translation_placeholders)
        except KeyError:
            return component_message

    return async_get_exception_message


def pytest_configure() -> None:
    """Patch the core test fixture to use RemoteHomeAssistant."""
    import tests.conftest as tests_conftest
    import tests.common as tests_common
    import homeassistant.components.ffmpeg as ffmpeg_component
    import homeassistant
    import homeassistant.core as ha_core
    import homeassistant.helpers.entity_platform as entity_platform_helper
    import homeassistant.exceptions as ha_exceptions
    import homeassistant.loader as ha_loader
    import homeassistant.helpers.translation as translation_helper
    from homeassistant.util.async_ import cancelling

    if getattr(tests_common, "_hass_client_patched", False):
        return

    original_async_test_home_assistant = tests_common.async_test_home_assistant
    original_async_get_component_strings = translation_helper._async_get_component_strings
    original_platform_get_translations = (
        entity_platform_helper.PlatformData._async_get_translations
    )
    original_entity_platform_setup = entity_platform_helper.EntityPlatform._async_setup_platform
    original_ffmpeg_get_version = ffmpeg_component.FFmpegManager.async_get_version
    from hass_client.runtime import RemoteHomeAssistant
    original_async_block_till_done = RemoteHomeAssistant.async_block_till_done
    original_create_task = RemoteHomeAssistant.create_task

    strings_resolver = _StringsResolver(Path(homeassistant.__file__).resolve().parent)
    fallback_exception_message = _build_exception_message_fallback(
        translation_helper.async_get_exception_message,
        strings_resolver,
    )

    def has_translations(self) -> bool:
        """Treat strings.json as a translation source for tests."""
        return (
            "translations" in self._top_level_files
            or "strings.json" in self._top_level_files
        )

    async def async_get_component_strings(hass, languages, components, integrations):
        """Load generated translations and synthesize English fallback from strings.json."""
        translations = await original_async_get_component_strings(
            hass, languages, components, integrations
        )

        if "en" not in languages:
            return translations

        english_translations = translations.setdefault("en", {})
        for domain in components:
            integration = integrations.get(domain)
            if integration is None:
                continue
            if (integration.file_path / "translations" / "en.json").is_file():
                continue
            synthesized = strings_resolver.resolve_component(domain)
            if not synthesized:
                continue
            _merge_missing_translations(
                english_translations.setdefault(domain, {}),
                synthesized,
            )

        return translations

    async def platform_get_translations(self, language, category, integration):
        """Delegate to the platform translation loader."""
        return await original_platform_get_translations(
            self, language, category, integration
        )

    async def entity_platform_setup(self, async_create_setup_awaitable, tries=0):
        """Preserve mocked call_at trace shape expected by core helper tests."""
        if isinstance(self.hass.loop.call_at, Mock):
            self.hass.loop.call_later(0, _noop_timer)
        return await original_entity_platform_setup(
            self, async_create_setup_awaitable, tries
        )

    async def async_block_till_done(self, wait_background_tasks: bool = False) -> None:
        """Avoid scheduling timeout handles when loop.call_later is mocked in tests."""
        if not isinstance(self.loop.call_later, Mock):
            await original_async_block_till_done(self, wait_background_tasks)
            return

        await asyncio.sleep(0)
        current_task = asyncio.current_task()
        while tasks := [
            task
            for task in (
                self._tasks | self._background_tasks
                if wait_background_tasks
                else self._tasks
            )
            if task is not current_task and not cancelling(task)
        ]:
            await asyncio.wait(tasks)

    def create_task(self, target, name=None) -> None:
        """Run eager task creation immediately when already on the loop thread."""
        if self.loop_thread_id == threading.get_ident() and not isinstance(
            self.loop.call_at, Mock
        ):
            self.async_create_task_internal(target, name, eager_start=True)
            return
        original_create_task(self, target, name)

    async def ffmpeg_get_version(self):
        """Avoid spawning subprocesses during ffmpeg setup in the compatibility suite."""
        if self._version is None:
            self._version = ffmpeg_component.OFFICIAL_IMAGE_VERSION
            self._major_version = int(self._version.split(".")[0])
        return self._version, self._major_version

    tests_common.HomeAssistant = RemoteHomeAssistant
    ha_core.HomeAssistant = RemoteHomeAssistant
    RemoteHomeAssistant.async_block_till_done = async_block_till_done
    RemoteHomeAssistant.create_task = create_task
    ffmpeg_component.FFmpegManager.async_get_version = ffmpeg_get_version
    has_translations_descriptor = cached_property(has_translations)
    has_translations_descriptor.__set_name__(
        ha_loader.Integration, "has_translations"
    )
    ha_loader.Integration.has_translations = has_translations_descriptor
    entity_platform_helper.PlatformData._async_get_translations = (
        platform_get_translations
    )
    entity_platform_helper.EntityPlatform._async_setup_platform = entity_platform_setup
    translation_helper._async_get_component_strings = async_get_component_strings
    translation_helper.async_get_exception_message = fallback_exception_message
    ha_exceptions._function_cache["async_get_exception_message"] = (
        fallback_exception_message
    )

    @asynccontextmanager
    async def async_test_home_assistant(*args, **kwargs):
        async with original_async_test_home_assistant(*args, **kwargs) as hass:
            if isinstance(hass, RemoteHomeAssistant):
                await hass.async_setup_remote()
            try:
                yield hass
            finally:
                if isinstance(hass, RemoteHomeAssistant):
                    await hass.async_teardown_remote()

    tests_common.async_test_home_assistant = async_test_home_assistant
    tests_conftest.async_test_home_assistant = async_test_home_assistant
    tests_common._hass_client_patched = True
