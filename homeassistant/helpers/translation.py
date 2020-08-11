"""Translation string lookup helpers."""
import asyncio
import logging
from typing import Any, Dict, Optional, Set

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, callback
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
    translation_strings: Dict[str, Dict[str, Any]], components: Set[str], category: str,
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

        cur_value = domain_resources.get(category)

        # If not exists, set value.
        if cur_value is None:
            domain_resources[category] = new_value

        # If exists, and a list, append
        elif isinstance(cur_value, list):
            cur_value.append(new_value)

        # If exists, and a dict make it a list with 2 entries.
        else:
            domain_resources[category] = [cur_value, new_value]

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
    translation_strings: Dict[str, Dict[str, Any]], components: Set[str], category: str,
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


class FlatCache:
    """Cache for flattened translations."""

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the cache."""
        self.hass = hass
        self.cache: Dict[str, Dict[str, Dict[str, str]]] = {}

    @callback
    def async_setup(self) -> None:
        """Initialize the cache clear listeners."""
        self.hass.bus.async_listen(EVENT_COMPONENT_LOADED, self._async_component_loaded)

    @callback
    def _async_component_loaded(self, event: Event) -> None:
        """Clear cache when a new component is loaded."""
        self.cache = {}

    @callback
    def async_get_cache(self, language: str, category: str) -> Optional[Dict[str, str]]:
        """Get cache."""
        return self.cache.setdefault(language, {}).get(category)

    @callback
    def async_set_cache(
        self, language: str, category: str, data: Dict[str, str]
    ) -> None:
        """Set cache."""
        self.cache.setdefault(language, {})[category] = data


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

    if integration is not None:
        components = {integration}
    elif config_flow:
        # When it's a config flow, we're going to merge the cached loaded component results
        # with the integrations that have not been loaded yet. We merge this at the end.
        # We can't cache with config flow, as we can't monitor it during runtime.
        components = (await async_get_config_flows(hass)) - hass.config.components
    else:
        # Only 'state' supports merging, so remove platforms from selection
        if category == "state":
            components = set(hass.config.components)
        else:
            components = {
                component
                for component in hass.config.components
                if "." not in component
            }

    async with lock:
        if integration is None and not config_flow:
            cache = hass.data.get(TRANSLATION_FLATTEN_CACHE)
            if cache is None:
                cache = hass.data[TRANSLATION_FLATTEN_CACHE] = FlatCache(hass)
                cache.async_setup()

            cached_translations = cache.async_get_cache(language, category)

            if cached_translations is not None:
                return cached_translations

        tasks = [async_get_component_strings(hass, language, components)]

        # Fetch the English resources, as a fallback for missing keys
        if language != "en":
            tasks.append(async_get_component_strings(hass, "en", components))

        _LOGGER.debug(
            "Cache miss for %s, %s: %s", language, category, ", ".join(components)
        )

        results = await asyncio.gather(*tasks)

    if category == "state":
        resource_func = merge_resources
    else:
        resource_func = build_resources

    resources = flatten(resource_func(results[0], components, category))

    if language != "en":
        base_resources = flatten(resource_func(results[1], components, category))
        resources = {**base_resources, **resources}

    if integration is not None:
        pass
    elif config_flow:
        loaded_comp_resources = await async_get_translations(hass, language, category)
        resources.update(loaded_comp_resources)
    else:
        assert cache is not None
        cache.async_set_cache(language, category, resources)

    return resources
