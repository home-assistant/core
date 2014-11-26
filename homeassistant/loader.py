"""
homeassistant.loader
~~~~~~~~~~~~~~~~~~~~

Provides methods for loading Home Assistant components.

This module has quite some complex parts. I have tried to add as much
documentation as possible to keep it understandable.

Components are loaded by calling get_component('switch') from your code.
If you want to retrieve a platform that is part of a component, you should
call get_component('switch.your_platform'). In both cases the config directory
is checked to see if it contains a user provided version. If not available it
will check the built-in components and platforms.
"""
import os
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
    custom_path = hass.get_config_path("custom_components")

    if os.path.isdir(custom_path):
        # Ensure we can load custom components using Pythons import
        sys.path.insert(0, hass.config_dir)

        # We cannot use the same approach as for built-in components because
        # custom components might only contain a platform for a component.
        # ie custom_components/switch/some_platform.py. Using pkgutil would
        # not give us the switch component (and neither should it).

        # Assumption: the custom_components dir only contains directories or
        # python components. If this assumption is not true, HA won't break,
        # just might output more errors.
        for fil in os.listdir(custom_path):
            if os.path.isdir(os.path.join(custom_path, fil)):
                AVAILABLE_COMPONENTS.append('custom_components.{}'.format(fil))

            else:
                AVAILABLE_COMPONENTS.append(
                    'custom_components.{}'.format(fil[0:-3]))


def set_component(comp_name, component):
    """ Sets a component in the cache. """
    _COMPONENT_CACHE[comp_name] = component


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
    # We do not want to silent the ImportErrors as they provide valuable
    # information to track down when debugging Home Assistant.

    # First check custom, then built-in
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
            module = importlib.import_module(path)

            # In Python 3 you can import files from directories that do not
            # contain the file __init__.py. A directory is a valid module if
            # it contains a file with the .py extension. In this case Python
            # will succeed in importing the directory as a module and call it
            # a namespace. We do not care about namespaces.
            # This prevents that when only
            # custom_components/switch/some_platform.py exists,
            # the import custom_components.switch would succeeed.
            if module.__spec__.origin == 'namespace':
                continue

            _LOGGER.info("Loaded %s from %s", comp_name, path)

            _COMPONENT_CACHE[comp_name] = module

            return module

        except ImportError:
            _LOGGER.exception(
                ("Error loading %s. Make sure all "
                 "dependencies are installed"), path)

    _LOGGER.error("Unable to find component %s", comp_name)

    return None
