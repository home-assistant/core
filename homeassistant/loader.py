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
    # Load the built-in components
    import homeassistant.components as components

    AVAILABLE_COMPONENTS.clear()

    AVAILABLE_COMPONENTS.extend(
        item[1] for item in
        pkgutil.iter_modules(components.__path__, 'homeassistant.components.'))

    # Look for available custom components

    # Ensure we can load custom components from the config dir
    sys.path.append(hass.config_dir)

    try:
        # pylint: disable=import-error
        import custom_components

        AVAILABLE_COMPONENTS.extend(
            item[1] for item in
            pkgutil.iter_modules(
                custom_components.__path__, 'custom_components.'))

    except ImportError:
        # No folder custom_components exist in the config directory
        pass


def get_component(comp_name):
    """ Tries to load specified component.
        Looks in config dir first, then built-in components.
        Only returns it if also found to be valid. """

    if comp_name in _COMPONENT_CACHE:
        return _COMPONENT_CACHE[comp_name]

    # If we ie. try to load custom_components.switch.wemo but the parent
    # custom_components.switch does not exist, importing it will trigger
    # an exception because it will try to import the parent.
    # Because of this behavior, we will approach loading sub components
    # with caution: only load it if we can verify that the parent exists.

    # First check config dir, then built-in
    potential_paths = ['custom_components.{}'.format(comp_name),
                       'homeassistant.components.{}'.format(comp_name)]

    for path in potential_paths:
        # Validate here that root component exists
        # If path contains a '.' we are specifying a sub-component
        # Using rsplit we get the parent component from sub-component
        root_comp = path.rsplit(".", 1)[0] if '.' in comp_name else path

        if root_comp not in AVAILABLE_COMPONENTS:
            continue

        try:
            _COMPONENT_CACHE[comp_name] = importlib.import_module(path)

            _LOGGER.info("Loaded %s from %s", comp_name, path)

            return _COMPONENT_CACHE[comp_name]
        except ImportError:
            _LOGGER.exception(
                ("Error loading %s. Make sure all "
                 "dependencies are installed"), path)

    # We did find components but were unable to load them
    _LOGGER.error("Unable to load component %s", comp_name)

    return None
