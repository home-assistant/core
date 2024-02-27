"""Translation string lookup helpers."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
import logging
import string
from typing import Any

from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
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


def _load_translations_files_by_language(
    translation_files: dict[str, dict[str, str]],
) -> dict[str, dict[str, Any]]:
    """Load and parse translation.json files."""
    loaded: dict[str, dict[str, Any]] = {}
    for language, component_translation_file in translation_files.items():
        loaded_for_language: dict[str, Any] = {}
        loaded[language] = loaded_for_language

        for component, translation_file in component_translation_file.items():
            loaded_json = load_json(translation_file)

            if not isinstance(loaded_json, dict):
                _LOGGER.warning(
                    "Translation file is unexpected type %s. Expected dict for %s",
                    type(loaded_json),
                    translation_file,
                )
                continue

            loaded_for_language[component] = loaded_json

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

        new_value = translation_strings.get(component, {}).get(category)

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
    translation_strings: dict[str, dict[str, dict[str, Any] | str]],
    components: set[str],
    category: str,
) -> dict[str, dict[str, Any] | str]:
    """Build the resources response for the given components."""
    # Build response
    return {
        component: category_strings
        for component in components
        if (component_strings := translation_strings.get(component))
        and (category_strings := component_strings.get(category))
    }


async def _async_get_component_strings(
    hass: HomeAssistant,
    languages: Iterable[str],
    components: set[str],
    integrations: dict[str, Integration],
) -> dict[str, dict[str, Any]]:
    """Load translations."""
    translations_by_language: dict[str, dict[str, Any]] = {}
    # Determine paths of missing components/platforms
    files_to_load_by_language: dict[str, dict[str, str]] = {}
    for language in languages:
        files_to_load: dict[str, str] = {}
        files_to_load_by_language[language] = files_to_load

        loaded_translations: dict[str, Any] = {}
        translations_by_language[language] = loaded_translations

        for loaded in components:
            domain = loaded.partition(".")[0]
            if not (integration := integrations.get(domain)):
                continue

            path = component_translation_path(loaded, language, integration)
            # No translation available
            if path is None:
                loaded_translations[loaded] = {}
            else:
                files_to_load[loaded] = path

    if not files_to_load:
        return translations_by_language

    # Load files
    loaded_translations_by_language = await hass.async_add_executor_job(
        _load_translations_files_by_language, files_to_load_by_language
    )

    # Translations that miss "title" will get integration put in.
    for language, loaded_translations in loaded_translations_by_language.items():
        for loaded, loaded_translation in loaded_translations.items():
            if "." in loaded:
                continue

            if "title" not in loaded_translation:
                loaded_translation["title"] = integrations[loaded].name

        translations_by_language[language].update(loaded_translations)

    return translations_by_language


class _TranslationCache:
    """Cache for flattened translations."""

    __slots__ = ("hass", "loaded", "cache", "lock")

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self.hass = hass
        self.loaded: dict[str, set[str]] = {}
        self.cache: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
        self.lock = asyncio.Lock()

    @callback
    def async_is_loaded(self, language: str, components: set[str]) -> bool:
        """Return if the given components are loaded for the language."""
        return components.issubset(self.loaded.get(language, set()))

    async def async_load(
        self,
        language: str,
        components: set[str],
    ) -> None:
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

    async def async_fetch(
        self,
        language: str,
        category: str,
        components: set[str],
    ) -> dict[str, str]:
        """Load resources into the cache and return them."""
        await self.async_load(language, components)

        return self.get_cached(language, category, components)

    def get_cached(
        self,
        language: str,
        category: str,
        components: set[str],
    ) -> dict[str, str]:
        """Read resources from the cache."""
        category_cache = self.cache.get(language, {}).get(category, {})
        # If only one component was requested, return it directly
        # to avoid merging the dictionaries and keeping additional
        # copies of the same data in memory.
        if len(components) == 1 and (component := next(iter(components))):
            return category_cache.get(component, {})

        result: dict[str, str] = {}
        for component in components.intersection(category_cache):
            result.update(category_cache[component])
        return result

    async def _async_load(self, language: str, components: set[str]) -> None:
        """Populate the cache for a given set of components."""
        _LOGGER.debug(
            "Cache miss for %s: %s",
            language,
            components,
        )
        # Fetch the English resources, as a fallback for missing keys
        languages = [LOCALE_EN] if language == LOCALE_EN else [LOCALE_EN, language]

        integrations: dict[str, Integration] = {}
        domains = {loaded.partition(".")[0] for loaded in components}
        ints_or_excs = await async_get_integrations(self.hass, domains)
        for domain, int_or_exc in ints_or_excs.items():
            if isinstance(int_or_exc, Exception):
                _LOGGER.warning(
                    "Failed to load integration for translation: %s", int_or_exc
                )
                continue
            integrations[domain] = int_or_exc

        translation_by_language_strings = await _async_get_component_strings(
            self.hass, languages, components, integrations
        )

        # English is always the fallback language so we load them first
        self._build_category_cache(
            language, components, translation_by_language_strings[LOCALE_EN]
        )

        if language != LOCALE_EN:
            # Now overlay the requested language on top of the English
            self._build_category_cache(
                language, components, translation_by_language_strings[language]
            )

            loaded_english_components = self.loaded.setdefault(LOCALE_EN, set())
            # Since we just loaded english anyway we can avoid loading
            # again if they switch back to english.
            if loaded_english_components.isdisjoint(components):
                self._build_category_cache(
                    LOCALE_EN, components, translation_by_language_strings[LOCALE_EN]
                )
                loaded_english_components.update(components)

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
            try:
                tuples = list(string.Formatter().parse(value))
            except ValueError:
                _LOGGER.error(
                    ("Error while parsing localized (%s) string %s"), language, key
                )
                continue
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

    If integration is specified, load it for that one.
    Otherwise, default to loaded integrations combined with config flow
    integrations if config_flow is true.
    """
    if integrations is None and config_flow:
        components = (await async_get_config_flows(hass)) - hass.config.components
    elif integrations is not None:
        components = set(integrations)
    else:
        components = _async_get_components(hass, category)

    return await _async_get_translations_cache(hass).async_fetch(
        language, category, components
    )


@callback
def async_get_cached_translations(
    hass: HomeAssistant,
    language: str,
    category: str,
    integration: str | None = None,
) -> dict[str, str]:
    """Return all cached backend translations.

    If integration is specified, return translations for it.
    Otherwise, default to all loaded integrations.
    """
    if integration is not None:
        components = {integration}
    else:
        components = _async_get_components(hass, category)

    return _async_get_translations_cache(hass).get_cached(
        language, category, components
    )


@callback
def _async_get_translations_cache(hass: HomeAssistant) -> _TranslationCache:
    """Return the translation cache."""
    cache: _TranslationCache = hass.data[TRANSLATION_FLATTEN_CACHE]
    return cache


_DIRECT_MAPPED_CATEGORIES = {"state", "entity_component", "services"}


@callback
def _async_get_components(
    hass: HomeAssistant,
    category: str,
) -> set[str]:
    """Return a set of components for which translations should be loaded."""
    if category in _DIRECT_MAPPED_CATEGORIES:
        return hass.config.components
    # Only 'state' supports merging, so remove platforms from selection
    return {component for component in hass.config.components if "." not in component}


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Create translation cache and register listeners for translation loaders.

    Listeners load translations for every loaded component and after config change.
    """
    cache = _TranslationCache(hass)
    current_language = hass.config.language
    hass.data[TRANSLATION_FLATTEN_CACHE] = cache

    @callback
    def _async_load_translations_filter(event: Event) -> bool:
        """Filter out unwanted events."""
        nonlocal current_language
        if (
            new_language := event.data.get("language")
        ) and new_language != current_language:
            current_language = new_language
            return True
        return False

    async def _async_load_translations(event: Event) -> None:
        new_language = event.data["language"]
        _LOGGER.debug("Loading translations for language: %s", new_language)
        await cache.async_load(new_language, hass.config.components)

    hass.bus.async_listen(
        EVENT_CORE_CONFIG_UPDATE,
        _async_load_translations,
        event_filter=_async_load_translations_filter,
    )


async def async_load_integrations(hass: HomeAssistant, integrations: set[str]) -> None:
    """Load translations for integrations."""
    await _async_get_translations_cache(hass).async_load(
        hass.config.language, integrations
    )


@callback
def async_translations_loaded(hass: HomeAssistant, components: set[str]) -> bool:
    """Return if the given components are loaded for the language."""
    return _async_get_translations_cache(hass).async_is_loaded(
        hass.config.language, components
    )


@callback
def async_translate_state(
    hass: HomeAssistant,
    state: str,
    domain: str,
    platform: str | None,
    translation_key: str | None,
    device_class: str | None,
) -> str:
    """Translate provided state using cached translations for currently selected language."""
    if state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
        return state
    language = hass.config.language
    if platform is not None and translation_key is not None:
        localize_key = (
            f"component.{platform}.entity.{domain}.{translation_key}.state.{state}"
        )
        translations = async_get_cached_translations(hass, language, "entity")
        if localize_key in translations:
            return translations[localize_key]

    translations = async_get_cached_translations(hass, language, "entity_component")
    if device_class is not None:
        localize_key = (
            f"component.{domain}.entity_component.{device_class}.state.{state}"
        )
        if localize_key in translations:
            return translations[localize_key]
    localize_key = f"component.{domain}.entity_component._.state.{state}"
    if localize_key in translations:
        return translations[localize_key]

    translations = async_get_cached_translations(hass, language, "state", domain)
    if device_class is not None:
        localize_key = f"component.{domain}.state.{device_class}.{state}"
        if localize_key in translations:
            return translations[localize_key]
    localize_key = f"component.{domain}.state._.{state}"
    if localize_key in translations:
        return translations[localize_key]

    return state
