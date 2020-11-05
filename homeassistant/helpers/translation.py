"""Translation string lookup helpers."""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from homeassistant.core import callback
from homeassistant.loader import (
    Integration,
    async_get_config_flows,
    async_get_integration,
    bind_hass,
)
from homeassistant.util.json import load_json

from .typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

TRANSLATION_LOAD_LOCK = "translation_load_lock"
TRANSLATION_FLATTEN_CACHE = "translation_flatten_cache"
LOCALE_EN = "en"


def recursive_flatten(prefix: Any, data: Dict) -> Dict[str, Any]:
    """Return a flattened representation of dict data."""
    output = {}
    for key, value in data.items():
        if isinstance(value, dict):
            output.update(recursive_flatten(f"{prefix}{key}.", value))
        else:
            output[f"{prefix}{key}"] = value
    return output


def flatten(data: Dict) -> Dict[str, Any]:
    """Return a flattened representation of dict data."""
    return recursive_flatten("", data)


@callback
def component_translation_path(
    component: str, language: str, integration: Integration
) -> Optional[str]:
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
    translation_files: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
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


def merge_resources(
    translation_strings: Dict[str, Dict[str, Any]],
    components: Set[str],
    category: str,
) -> Dict[str, Dict[str, Any]]:
    """Build and merge the resources response for the given components and platforms."""
    # Build response
    resources: Dict[str, Dict[str, Any]] = {}
    for component in components:
        if "." not in component:
            domain = component
        else:
            domain = component.split(".", 1)[0]

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

        domain_resources.setdefault(category, []).append(new_value)

    # Merge all the lists
    for domain, domain_resources in list(resources.items()):
        if not isinstance(domain_resources.get(category), list):
            continue

        merged = {}
        for entry in domain_resources[category]:
            if isinstance(entry, dict):
                merged.update(entry)
            else:
                _LOGGER.error(
                    "An integration providing translations for %s provided invalid data: %s",
                    domain,
                    entry,
                )
        domain_resources[category] = merged

    return {"component": resources}


def build_resources(
    translation_strings: Dict[str, Dict[str, Any]],
    components: Set[str],
    category: str,
) -> Dict[str, Dict[str, Any]]:
    """Build the resources response for the given components."""
    # Build response
    resources: Dict[str, Dict[str, Any]] = {}
    for component in components:
        new_value = translation_strings[component].get(category)

        if new_value is None:
            continue

        resources[component] = {category: new_value}

    return {"component": resources}


async def async_get_component_strings(
    hass: HomeAssistantType, language: str, components: Set[str]
) -> Dict[str, Any]:
    """Load translations."""
    domains = list({loaded.split(".")[-1] for loaded in components})
    integrations = dict(
        zip(
            domains,
            await asyncio.gather(
                *[async_get_integration(hass, domain) for domain in domains]
            ),
        )
    )

    translations: Dict[str, Any] = {}

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


class TranslationCache:
    """Cache for flattened translations."""

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the cache."""
        self.hass = hass
        self.cache: Dict[str, Dict[str, Tuple[Set[str], Dict[str, str]]]] = {}

    @callback
    def async_get_cache(
        self, language: str, category: str
    ) -> Optional[Tuple[Set[str], Dict[str, str]]]:
        """Get cache."""
        return self.cache.setdefault(language, {}).get(category)

    @callback
    def async_set_cache(
        self, language: str, category: str, components: Set[str], data: Dict[str, str]
    ) -> None:
        """Set cache."""
        self.cache.setdefault(language, {})[category] = (components, data)


@bind_hass
async def async_get_translations(
    hass: HomeAssistantType,
    language: str,
    category: str,
    integration: Optional[str] = None,
    config_flow: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return all backend translations.

    If integration specified, load it for that one.
    Otherwise default to loaded intgrations combined with config flow
    integrations if config_flow is true.
    """
    lock = hass.data.get(TRANSLATION_LOAD_LOCK)
    if lock is None:
        lock = hass.data[TRANSLATION_LOAD_LOCK] = asyncio.Lock()

    load_func = _async_load_translations
    resource_func = build_resources

    if integration is not None:
        components = {integration}
    elif config_flow:
        # When it's a config flow, we're going to merge the cached loaded component results
        # with the integrations that have not been loaded yet. We merge this at the end.
        # We can't cache with config flow, as we can't monitor it during runtime.
        components = (await async_get_config_flows(hass)) - hass.config.components
    else:
        load_func = _async_cached_load_translations
        # Only 'state' supports merging, so remove platforms from selection
        if category == "state":
            resource_func = merge_resources
            components = set(hass.config.components)
        else:
            components = {
                component
                for component in hass.config.components
                if "." not in component
            }

    async with lock:
        resources = await load_func(hass, resource_func, language, category, components)

    if config_flow:
        loaded_comp_resources = await async_get_translations(hass, language, category)
        resources.update(loaded_comp_resources)

    return resources


async def _async_load_translations(
    hass: HomeAssistantType,
    resource_func: Callable,
    language: str,
    category: str,
    components: Set,
) -> Dict[str, Any]:
    results = await _async_gather_load_tasks(hass, language, components)

    resources = flatten(resource_func(results[0], components, category))

    if language == LOCALE_EN:
        return resources

    base_resources = flatten(resource_func(results[1], components, category))
    return {**base_resources, **resources}


async def _async_cached_load_translations(
    hass: HomeAssistantType,
    resource_func: Callable,
    language: str,
    category: str,
    components: Set,
) -> Dict[str, Any]:
    cache = hass.data.get(TRANSLATION_FLATTEN_CACHE)
    if cache is None:
        cache = hass.data[TRANSLATION_FLATTEN_CACHE] = TranslationCache(hass)

    cached_translations = {}
    cache_entry = cache.async_get_cache(language, category)

    if cache_entry is not None:
        cached_components, cached_translations = cache_entry
        if cached_components == components:
            return cached_translations
        components_to_load = components - cached_components
    else:
        components_to_load = components

    _LOGGER.debug(
        "Cache miss for %s, %s: %s",
        language,
        category,
        ", ".join(components_to_load),
    )

    resources = {
        **cached_translations,
        **(
            await _async_load_translations(
                hass, resource_func, language, category, components_to_load
            )
        ),
    }

    # The cache must be set while holding the lock
    cache.async_set_cache(language, category, components, resources)

    return resources


async def _async_gather_load_tasks(
    hass: HomeAssistantType, language: str, components: Set
) -> List[Dict[str, Any]]:
    # Fetch the English resources, as a fallback for missing keys
    languages = [LOCALE_EN] if language == LOCALE_EN else [language, LOCALE_EN]

    results: List[Dict[str, Any]] = await asyncio.gather(
        *[async_get_component_strings(hass, lang, components) for lang in languages]
    )
    return results
