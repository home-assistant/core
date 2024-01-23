"""Translation string lookup helpers."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
import logging
import string
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import (
    Integration,
    async_get_config_flows,
    async_get_integrations,
    bind_hass,
)
from homeassistant.util.json import load_json

_LOGGER = logging.getLogger(__name__)

TRANSLATION_FLATTEN_CACHE = "translation_flatten_cache"
LOCALE_EN = "en"


def recursive_flatten(prefix: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Return a flattened representation of dict data."""
    output = {}
    for key, value in data.items():
        if isinstance(value, dict):
            output.update(recursive_flatten(f"{prefix}{key}.", value))
        else:
            output[f"{prefix}{key}"] = value
    return output


@callback
def component_translation_path(
    component: str, language: str, integration: Integration
) -> str | None:
    """Return the translation json file location for a component.

    For component:
     - components/hue/translations/nl.json

    For platform:
     - components/hue/translations/light.nl.json

    If component is just a single file, will return None.
    """
    parts = component.split(".")
    domain = parts[0]
    is_platform = len(parts) == 2

    # If it's a component that is just one file, we don't support translations
    # Example custom_components/my_component.py
    if integration.file_path.name != domain:
        return None

    if is_platform:
        filename = f"{parts[1]}.{language}.json"
    else:
        filename = f"{language}.json"

    translation_path = integration.file_path / "translations"

    return str(translation_path / filename)


def load_translations_files(
    translation_files: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Load and parse translation.json files."""
    loaded = {}
    for component, translation_file in translation_files.items():
        loaded_json = load_json(translation_file)

        if not isinstance(loaded_json, dict):
            _LOGGER.warning(
                "Translation file is unexpected type %s. Expected dict for %s",
                type(loaded_json),
                translation_file,
            )
            continue

        loaded[component] = loaded_json

    return loaded


def _merge_resources(
    translation_strings: dict[str, dict[str, Any]],
    components: set[str],
    category: str,
) -> dict[str, dict[str, Any]]:
    """Build and merge the resources response for the given components and platforms."""
    # Build response
    resources: dict[str, dict[str, Any]] = {}
    for component in components:
        domain = component.rpartition(".")[-1]

        domain_resources = resources.setdefault(domain, {})

        # Integrations are able to provide translations for their entities under other
        # integrations if they don't have an existing device class. This is done by
        # using a custom device class prefixed with their domain and two underscores.
        # These files are in platform specific files in the integration folder with
        # names like `strings.sensor.json`.
        # We are going to merge the translations for the custom device classes into
        # the translations of sensor.

        new_value = translation_strings[component].get(category)

        if new_value is None:
            continue

        if isinstance(new_value, dict):
            domain_resources.update(new_value)
        else:
            _LOGGER.error(
                (
                    "An integration providing translations for %s provided invalid"
                    " data: %s"
                ),
                domain,
                new_value,
            )

    return resources


def build_resources(
    translation_strings: dict[str, dict[str, Any]],
    components: set[str],
    category: str,
) -> dict[str, dict[str, Any] | str]:
    """Build the resources response for the given components."""
    # Build response
    return {
        component: translation_strings[component][category]
        for component in components
        if category in translation_strings[component]
        and translation_strings[component][category] is not None
    }


async def _async_get_component_strings(
    hass: HomeAssistant,
    language: str,
    components: set[str],
    integrations: dict[str, Integration],
) -> dict[str, Any]:
    """Load translations."""
    translations: dict[str, Any] = {}
    # Determine paths of missing components/platforms
    files_to_load = {}
    for loaded in components:
        domain = loaded.partition(".")[0]
        integration = integrations[domain]

        path = component_translation_path(loaded, language, integration)
        # No translation available
        if path is None:
            translations[loaded] = {}
        else:
            files_to_load[loaded] = path

    if not files_to_load:
        return translations

    # Load files
    load_translations_job = hass.async_add_executor_job(
        load_translations_files, files_to_load
    )
    assert load_translations_job is not None
    loaded_translations = await load_translations_job

    # Translations that miss "title" will get integration put in.
    for loaded, loaded_translation in loaded_translations.items():
        if "." in loaded:
            continue

        if "title" not in loaded_translation:
            loaded_translation["title"] = integrations[loaded].name

    translations.update(loaded_translations)

    return translations


class _TranslationCache:
    """Cache for flattened translations."""

    __slots__ = ("hass", "loaded", "cache", "lock")

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self.hass = hass
        self.loaded: dict[str, set[str]] = {}
        self.cache: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
        self.lock = asyncio.Lock()

    async def async_fetch(
        self,
        language: str,
        category: str,
        components: set[str],
    ) -> dict[str, str]:
        """Load resources into the cache."""
        loaded = self.loaded.setdefault(language, set())
        if components_to_load := components - loaded:
            # Translations are never unloaded so if there are no components to load
            # we can skip the lock which reduces contention when multiple different
            # translations categories are being fetched at the same time which is
            # common from the frontend.
            async with self.lock:
                # Check components to load again, as another task might have loaded
                # them while we were waiting for the lock.
                if components_to_load := components - loaded:
                    await self._async_load(language, components_to_load)

        result: dict[str, str] = {}
        category_cache = self.cache.get(language, {}).get(category, {})
        for component in components.intersection(category_cache):
            result.update(category_cache[component])
        return result

    async def _async_load(self, language: str, components: set[str]) -> None:
        """Populate the cache for a given set of components."""
        _LOGGER.debug(
            "Cache miss for %s: %s",
            language,
            ", ".join(components),
        )
        # Fetch the English resources, as a fallback for missing keys
        languages = [LOCALE_EN] if language == LOCALE_EN else [LOCALE_EN, language]

        integrations: dict[str, Integration] = {}
        domains = list({loaded.partition(".")[0] for loaded in components})
        ints_or_excs = await async_get_integrations(self.hass, domains)
        for domain, int_or_exc in ints_or_excs.items():
            if isinstance(int_or_exc, Exception):
                raise int_or_exc
            integrations[domain] = int_or_exc

        for translation_strings in await asyncio.gather(
            *(
                _async_get_component_strings(self.hass, lang, components, integrations)
                for lang in languages
            )
        ):
            self._build_category_cache(language, components, translation_strings)

        self.loaded[language].update(components)

    def _validate_placeholders(
        self,
        language: str,
        updated_resources: dict[str, Any],
        cached_resources: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate if updated resources have same placeholders as cached resources."""
        if cached_resources is None:
            return updated_resources

        mismatches: set[str] = set()

        for key, value in updated_resources.items():
            if key not in cached_resources:
                continue
            tuples = list(string.Formatter().parse(value))
            updated_placeholders = {tup[1] for tup in tuples if tup[1] is not None}

            tuples = list(string.Formatter().parse(cached_resources[key]))
            cached_placeholders = {tup[1] for tup in tuples if tup[1] is not None}
            if updated_placeholders != cached_placeholders:
                _LOGGER.error(
                    (
                        "Validation of translation placeholders for localized (%s) string "
                        "%s failed"
                    ),
                    language,
                    key,
                )
                mismatches.add(key)

        for mismatch in mismatches:
            del updated_resources[mismatch]

        return updated_resources

    @callback
    def _build_category_cache(
        self,
        language: str,
        components: set[str],
        translation_strings: dict[str, dict[str, Any]],
    ) -> None:
        """Extract resources into the cache."""
        resource: dict[str, Any] | str
        cached = self.cache.setdefault(language, {})

        categories: set[str] = set()
        for resource in translation_strings.values():
            categories.update(resource)

        for category in categories:
            new_resources: Mapping[str, dict[str, Any] | str]

            if category in ("state", "entity_component"):
                new_resources = _merge_resources(
                    translation_strings, components, category
                )
            else:
                new_resources = build_resources(
                    translation_strings, components, category
                )

            category_cache = cached.setdefault(category, {})

            for component, resource in new_resources.items():
                component_cache = category_cache.setdefault(component, {})

                if isinstance(resource, dict):
                    resources_flatten = recursive_flatten(
                        f"component.{component}.{category}.",
                        resource,
                    )
                    resources_flatten = self._validate_placeholders(
                        language, resources_flatten, component_cache
                    )
                    component_cache.update(resources_flatten)
                else:
                    component_cache[f"component.{component}.{category}"] = resource


@bind_hass
async def async_get_translations(
    hass: HomeAssistant,
    language: str,
    category: str,
    integrations: Iterable[str] | None = None,
    config_flow: bool | None = None,
) -> dict[str, str]:
    """Return all backend translations.

    If integration specified, load it for that one.
    Otherwise default to loaded integrations combined with config flow
    integrations if config_flow is true.
    """
    if integrations is not None:
        components = set(integrations)
    elif config_flow:
        components = (await async_get_config_flows(hass)) - hass.config.components
    elif category in ("state", "entity_component", "services"):
        components = hass.config.components
    else:
        # Only 'state' supports merging, so remove platforms from selection
        components = {
            component for component in hass.config.components if "." not in component
        }

    if TRANSLATION_FLATTEN_CACHE in hass.data:
        cache: _TranslationCache = hass.data[TRANSLATION_FLATTEN_CACHE]
    else:
        cache = hass.data[TRANSLATION_FLATTEN_CACHE] = _TranslationCache(hass)

    return await cache.async_fetch(language, category, components)
