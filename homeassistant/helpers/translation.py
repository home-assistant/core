"""Translation string lookup helpers."""
import asyncio
import logging
from typing import Any, Dict, Optional, Set

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
TRANSLATION_STRING_CACHE = "translation_string_cache"


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
     - components/hue/.translations/nl.json

    For platform:
     - components/hue/.translations/light.nl.json

    If component is just a single file, will return None.
    """
    parts = component.split(".")
    domain = parts[-1]
    is_platform = len(parts) == 2

    if is_platform:
        filename = f"{parts[0]}.{language}.json"
        return str(integration.file_path / ".translations" / filename)

    # If it's a component that is just one file, we don't support translations
    # Example custom_components/my_component.py
    if integration.file_path.name != domain:
        return None

    filename = f"{language}.json"
    return str(integration.file_path / ".translations" / filename)


def load_translations_files(
    translation_files: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """Load and parse translation.json files."""
    loaded = {}
    for component, translation_file in translation_files.items():
        loaded_json = load_json(translation_file)
        assert isinstance(loaded_json, dict)
        loaded[component] = loaded_json

    return loaded


def build_resources(
    translation_cache: Dict[str, Dict[str, Any]], components: Set[str], category: str,
) -> Dict[str, Dict[str, Any]]:
    """Build the resources response for the given components."""
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

        new_value = translation_cache[component].get(category)

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


async def async_get_component_cache(
    hass: HomeAssistantType, language: str, components: Set[str]
) -> Dict[str, Any]:
    """Return translation cache that includes all specified components."""
    # Get cache for this language
    cache: Dict[str, Dict[str, Any]] = hass.data.setdefault(
        TRANSLATION_STRING_CACHE, {}
    )
    translation_cache: Dict[str, Any] = cache.setdefault(language, {})

    # Calculate the missing components and platforms
    missing_loaded = components - set(translation_cache)

    if not missing_loaded:
        return translation_cache

    missing_domains = list({loaded.split(".")[-1] for loaded in missing_loaded})
    missing_integrations = dict(
        zip(
            missing_domains,
            await asyncio.gather(
                *[async_get_integration(hass, domain) for domain in missing_domains]
            ),
        )
    )

    # Determine paths of missing components/platforms
    missing_files = {}
    for loaded in missing_loaded:
        parts = loaded.split(".")
        domain = parts[-1]
        integration = missing_integrations[domain]

        path = component_translation_path(loaded, language, integration)
        # No translation available
        if path is None:
            translation_cache[loaded] = {}
        else:
            missing_files[loaded] = path

    # Load missing files
    if missing_files:
        load_translations_job = hass.async_add_job(
            load_translations_files, missing_files
        )
        assert load_translations_job is not None
        loaded_translations = await load_translations_job

        # Translations that miss "title" will get integration put in.
        for loaded, translations in loaded_translations.items():
            if "." in loaded:
                continue

            if "title" not in translations:
                translations["title"] = missing_integrations[loaded].name

        # Update cache
        translation_cache.update(loaded_translations)

    return translation_cache


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
    if integration is not None:
        components = {integration}
    elif config_flow:
        components = hass.config.components | await async_get_config_flows(hass)
    else:
        components = set(hass.config.components)

    lock = hass.data.get(TRANSLATION_LOAD_LOCK)
    if lock is None:
        lock = hass.data[TRANSLATION_LOAD_LOCK] = asyncio.Lock()

    tasks = [async_get_component_cache(hass, language, components)]

    # Fetch the English resources, as a fallback for missing keys
    if language != "en":
        tasks.append(async_get_component_cache(hass, "en", components))

    async with lock:
        results = await asyncio.gather(*tasks)

    resources = flatten(build_resources(results[0], components, category))

    if language != "en":
        base_resources = flatten(build_resources(results[1], components, category))
        resources = {**base_resources, **resources}

    return resources
