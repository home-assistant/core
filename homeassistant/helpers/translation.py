"""Translation string lookup helpers."""
import asyncio
import logging
# pylint: disable=unused-import
from typing import Optional  # NOQA
from os import path

from homeassistant.loader import get_component, bind_hass
from homeassistant.util.json import load_json

_LOGGER = logging.getLogger(__name__)

TRANSLATION_STRING_CACHE = 'translation_string_cache'


def recursive_flatten(prefix, data):
    """Return a flattened representation of dict data."""
    output = {}
    for key, value in data.items():
        if isinstance(value, dict):
            output.update(
                recursive_flatten('{}{}.'.format(prefix, key), value))
        else:
            output['{}{}'.format(prefix, key)] = value
    return output


def flatten(data):
    """Return a flattened representation of dict data."""
    return recursive_flatten('', data)


@asyncio.coroutine
@bind_hass
def async_get_translations(hass, language):
    """Return translations for all components."""
    if TRANSLATION_STRING_CACHE not in hass.data:
        hass.data[TRANSLATION_STRING_CACHE] = {}
    if language not in hass.data[TRANSLATION_STRING_CACHE]:
        hass.data[TRANSLATION_STRING_CACHE][language] = {}
    translation_cache = hass.data[TRANSLATION_STRING_CACHE][language]

    def component_translation_file(component):
        """Return the translation json file location for a component."""
        component_path = path.dirname(get_component(component).__file__)
        # Temporarily load the English source files, instead of the Lokalise
        # downloaded files for the requested language.
        if '.' in component:
            platform = component.split('.', 1)[1]
            filename = 'strings.{}.json'.format(platform)
        else:
            filename = 'strings.json'
        return path.join(component_path, filename)

    def load_translations_files(translation_files):
        """Load and parse translation.json files."""
        loaded = {}
        for translation_file in translation_files:
            try:
                loaded[translation_file] = load_json(translation_file)
            except FileNotFoundError:
                loaded[translation_file] = {}

        return loaded

    # Get the set of components
    components = hass.config.components

    # Load missing files
    missing = set()
    for component in components:
        if component not in translation_cache:
            missing.add(component_translation_file(component))

    if missing:
        loaded = yield from hass.async_add_job(
            load_translations_files, missing)

    # Update cache
    for component in components:
        if component not in translation_cache:
            json_file = component_translation_file(component)
            translation_cache[component] = loaded[json_file]

    # Build response
    resources = {}
    for component in components:
        if '.' not in component:
            domain = component
        else:
            domain = component.split('.', 1)[0]

        if domain not in resources:
            resources[domain] = {}

        # Add the translations for this component to the domain resources.
        # Since clients cannot determine which platform an entity belongs to,
        # all translations for a domain will be returned together.
        resources[domain].update(translation_cache[component])

    # Return the component translations resources under the 'component'
    # translation namespace
    return flatten({'component': resources})
