"""
homeassistant.loader
~~~~~~~~~~~~~~~~~~~~

Provides methods for loading Home Assistant components.
"""
import sys
import pkgutil
import importlib
import logging

# List of available components
AVAILABLE_COMPONENTS = []

# Dict of loaded components mapped name => module
_COMPONENT_CACHE = {}

_LOGGER = logging.getLogger(__name__)


def prepare(hass):
    """ Prepares the loading of components. """
    # Ensure we can load custom components from the config dir
    sys.path.append(hass.config_dir)

    # pylint: disable=import-error
    import custom_components
    import homeassistant.components as components

    AVAILABLE_COMPONENTS.clear()

    AVAILABLE_COMPONENTS.extend(
        item[1] for item in
        pkgutil.iter_modules(components.__path__, 'homeassistant.components.'))

    AVAILABLE_COMPONENTS.extend(
        item[1] for item in
        pkgutil.iter_modules(custom_components.__path__, 'custom_components.'))


def get_component(comp_name):
    """ Tries to load specified component.
        Looks in config dir first, then built-in components.
        Only returns it if also found to be valid. """

    if comp_name in _COMPONENT_CACHE:
        return _COMPONENT_CACHE[comp_name]

    # First check config dir, then built-in
    potential_paths = [path for path in
                       ['custom_components.{}'.format(comp_name),
                        'homeassistant.components.{}'.format(comp_name)]
                       if path in AVAILABLE_COMPONENTS]

    if not potential_paths:
        _LOGGER.error("Failed to find component {}".format(comp_name))

        return None

    for path in potential_paths:
        comp = _get_component(path)

        if comp is not None:
            _LOGGER.info("Loaded component {} from {}".format(
                comp_name, path))

            _COMPONENT_CACHE[comp_name] = comp

            return comp

    # We did find components but were unable to load them
    _LOGGER.error("Unable to load component {}".format(comp_name))

    return None


def _get_component(module):
    """ Tries to load specified component.
        Only returns it if also found to be valid."""
    try:
        comp = importlib.import_module(module)

    except ImportError:
        _LOGGER.exception("Error loading {}".format(module))

        return None

    # Validation if component has required methods and attributes
    errors = []

    if not hasattr(comp, 'DOMAIN'):
        errors.append("missing DOMAIN attribute")

    if not hasattr(comp, 'DEPENDENCIES'):
        errors.append("missing DEPENDENCIES attribute")

    if not hasattr(comp, 'setup'):
        errors.append("missing setup method")

    if errors:
        _LOGGER.error("Found invalid component {}: {}".format(
            module, ", ".join(errors)))

        return None

    else:
        return comp
