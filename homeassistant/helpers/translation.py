"""Translation string lookup helpers."""
import asyncio
import logging
from typing import Any, Dict, Iterable, Optional

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
def component_translation_file(
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
    translation_cache: Dict[str, Dict[str, Any]], components: Iterable[str]
) -> Dict[str, Dict[str, Any]]:
    """Build the resources response for the given components."""
    # Build response
    resources: Dict[str, Dict[str, Any]] = {}
    for component in components:
        if "." not in component:
            domain = component
        else:
            domain = component.split(".", 1)[0]

        if domain not in resources:
            resources[domain] = {}

        # Add the translations for this component to the domain resources.
        # Since clients cannot determine which platform an entity belongs to,
        # all translations for a domain will be returned together.
        resources[domain].update(translation_cache[component])

    return resources


@bind_hass
async def async_get_component_resources(
    hass: HomeAssistantType, language: str
) -> Dict[str, Any]:
    """Return translation resources for all components.

    We go through all loaded components and platforms:
     - see if they have already been loaded (exist in translation_cache)
     - load them if they have not been loaded yet
     - write them to cache
     - flatten the cache and return
    """
    # Get cache for this language
    cache = hass.data.setdefault(TRANSLATION_STRING_CACHE, {})
    translation_cache = cache.setdefault(language, {})

    # Get the set of components to check
    components = hass.config.components | await async_get_config_flows(hass)

    # Calculate the missing components and platforms
    missing_loaded = components - set(translation_cache)
    missing_domains = {loaded.split(".")[-1] for loaded in missing_loaded}

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

        path = component_translation_file(loaded, language, integration)
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

    resources = build_resources(translation_cache, components)

    # Return the component translations resources under the 'component'
    # translation namespace
    return flatten({"component": resources})


@bind_hass
async def async_get_translations(
    hass: HomeAssistantType, language: str
) -> Dict[str, Any]:
    """Return all backend translations."""
    resources = await async_get_component_resources(hass, language)
    if language != "en":
        # Fetch the English resources, as a fallback for missing keys
        base_resources = await async_get_component_resources(hass, "en")
        resources = {**base_resources, **resources}

    return resources
