"""Translation string lookup helpers."""
from __future__ import annotations

import asyncio
from collections import ChainMap
from collections.abc import Iterable, Mapping
import logging
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

TRANSLATION_LOAD_LOCK = "translation_load_lock"
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
    domain = parts[-1]
    is_platform = len(parts) == 2

    # If it's a component that is just one file, we don't support translations
    # Example custom_components/my_component.py
    if integration.file_path.name != domain:
        return None

    if is_platform:
        filename = f"{parts[0]}.{language}.json"
    else:
        filename = f"{language}.json"

    translation_path = integration.file_path / "translations"

    return str(translation_path / filename)


def load_translations_files(
    translation_files: dict[str, str]
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
        domain = component.partition(".")[0]

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
                "An integration providing translations for %s provided invalid data: %s",
                domain,
                new_value,
            )

    return resources


def _build_resources(
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


async def async_get_component_strings(
    hass: HomeAssistant, language: str, components: set[str]
) -> dict[str, Any]:
    """Load translations."""
    domains = list({loaded.rpartition(".")[-1] for loaded in components})

    integrations: dict[str, Integration] = {}
    ints_or_excs = await async_get_integrations(hass, domains)
    for domain, int_or_exc in ints_or_excs.items():
        if isinstance(int_or_exc, Exception):
            raise int_or_exc
        integrations[domain] = int_or_exc
    translations: dict[str, Any] = {}

    # Determine paths of missing components/platforms
    files_to_load = {}
    for loaded in components:
        parts = loaded.split(".")
        domain = parts[-1]
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

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self.hass = hass
        self.loaded: dict[str, set[str]] = {}
        self.cache: dict[str, dict[str, dict[str, Any]]] = {}

    async def async_fetch(
        self,
        language: str,
        category: str,
        components: set[str],
    ) -> list[dict[str, dict[str, Any]]]:
        """Load resources into the cache."""
        components_to_load = components - self.loaded.setdefault(language, set())

        if components_to_load:
            await self._async_load(language, components_to_load)

        cached = self.cache.get(language, {})

        return [cached.get(component, {}).get(category, {}) for component in components]

    async def _async_load(self, language: str, components: set[str]) -> None:
        """Populate the cache for a given set of components."""
        _LOGGER.debug(
            "Cache miss for %s: %s",
            language,
            ", ".join(components),
        )
        # Fetch the English resources, as a fallback for missing keys
        languages = [LOCALE_EN] if language == LOCALE_EN else [LOCALE_EN, language]
        for translation_strings in await asyncio.gather(
            *(
                async_get_component_strings(self.hass, lang, components)
                for lang in languages
            )
        ):
            self._build_category_cache(language, components, translation_strings)

        self.loaded[language].update(components)

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
            resource_func = (
                _merge_resources if category == "state" else _build_resources
            )
            new_resources: Mapping[str, dict[str, Any] | str]
            new_resources = resource_func(translation_strings, components, category)  # type: ignore[assignment]

            for component, resource in new_resources.items():
                category_cache: dict[str, Any] = cached.setdefault(
                    component, {}
                ).setdefault(category, {})

                if isinstance(resource, dict):
                    category_cache.update(
                        recursive_flatten(
                            f"component.{component}.{category}.",
                            resource,
                        )
                    )
                else:
                    category_cache[f"component.{component}.{category}"] = resource


@bind_hass
async def async_get_translations(
    hass: HomeAssistant,
    language: str,
    category: str,
    integrations: Iterable[str] | None = None,
    config_flow: bool | None = None,
) -> dict[str, Any]:
    """Return all backend translations.

    If integration specified, load it for that one.
    Otherwise default to loaded intgrations combined with config flow
    integrations if config_flow is true.
    """
    lock = hass.data.setdefault(TRANSLATION_LOAD_LOCK, asyncio.Lock())

    if integrations is not None:
        components = set(integrations)
    elif config_flow:
        components = (await async_get_config_flows(hass)) - hass.config.components
    elif category == "state":
        components = set(hass.config.components)
    else:
        # Only 'state' supports merging, so remove platforms from selection
        components = {
            component for component in hass.config.components if "." not in component
        }

    async with lock:
        if TRANSLATION_FLATTEN_CACHE in hass.data:
            cache = hass.data[TRANSLATION_FLATTEN_CACHE]
        else:
            cache = hass.data[TRANSLATION_FLATTEN_CACHE] = _TranslationCache(hass)
        cached = await cache.async_fetch(language, category, components)

    return dict(ChainMap(*cached))
