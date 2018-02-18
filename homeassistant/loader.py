"""
The methods for loading Home Assistant components.

This module has quite some complex parts. I have tried to add as much
documentation as possible to keep it understandable.

Components can be accessed via hass.components.switch from your code.
If you want to retrieve a platform that is part of a component, you should
call get_component('switch.your_platform'). In both cases the config directory
is checked to see if it contains a user provided version. If not available it
will check the built-in components and platforms.
"""
import functools as ft
import importlib
import logging
import os
import pkgutil
import sys
from types import ModuleType

# pylint: disable=unused-import
from typing import Dict, List, Optional, Sequence, Set  # NOQA

from homeassistant.const import PLATFORM_FORMAT
from homeassistant.util import OrderedSet

# Typing imports
# pylint: disable=using-constant-test,unused-import
if False:
    from homeassistant.core import HomeAssistant  # NOQA

PREPARED = False

DEPENDENCY_BLACKLIST = set(('config',))

# List of available components
AVAILABLE_COMPONENTS = []  # type: List[str]

# Dict of loaded components mapped name => module
_COMPONENT_CACHE = {}  # type: Dict[str, ModuleType]

_LOGGER = logging.getLogger(__name__)


def prepare(hass: 'HomeAssistant'):
    """Prepare the loading of components.

    This method needs to run in an executor.
    """
    global PREPARED  # pylint: disable=global-statement

    # Load the built-in components
    import homeassistant.components as components

    AVAILABLE_COMPONENTS.clear()

    AVAILABLE_COMPONENTS.extend(
        item[1] for item in
        pkgutil.iter_modules(components.__path__, 'homeassistant.components.'))

    # Look for available custom components
    custom_path = hass.config.path("custom_components")

    if os.path.isdir(custom_path):
        # Ensure we can load custom components using Pythons import
        sys.path.insert(0, hass.config.config_dir)

        # We cannot use the same approach as for built-in components because
        # custom components might only contain a platform for a component.
        # ie custom_components/switch/some_platform.py. Using pkgutil would
        # not give us the switch component (and neither should it).

        # Assumption: the custom_components dir only contains directories or
        # python components. If this assumption is not true, HA won't break,
        # just might output more errors.
        for fil in os.listdir(custom_path):
            if fil == '__pycache__':
                continue
            elif os.path.isdir(os.path.join(custom_path, fil)):
                AVAILABLE_COMPONENTS.append('custom_components.{}'.format(fil))
            else:
                # For files we will strip out .py extension
                AVAILABLE_COMPONENTS.append(
                    'custom_components.{}'.format(fil[0:-3]))

    PREPARED = True


def set_component(comp_name: str, component: ModuleType) -> None:
    """Set a component in the cache.

    Async friendly.
    """
    _check_prepared()

    _COMPONENT_CACHE[comp_name] = component


def get_platform(domain: str, platform: str) -> Optional[ModuleType]:
    """Try to load specified platform.

    Async friendly.
    """
    return get_component(PLATFORM_FORMAT.format(domain, platform))


def get_component(comp_name) -> Optional[ModuleType]:
    """Try to load specified component.

    Looks in config dir first, then built-in components.
    Only returns it if also found to be valid.

    Async friendly.
    """
    if comp_name in _COMPONENT_CACHE:
        return _COMPONENT_CACHE[comp_name]

    _check_prepared()

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
            # the import custom_components.switch would succeed.
            if module.__spec__.origin == 'namespace':
                continue

            _LOGGER.info("Loaded %s from %s", comp_name, path)

            _COMPONENT_CACHE[comp_name] = module

            return module

        except ImportError as err:
            # This error happens if for example custom_components/switch
            # exists and we try to load switch.demo.
            if str(err) != "No module named '{}'".format(path):
                _LOGGER.exception(
                    ("Error loading %s. Make sure all "
                     "dependencies are installed"), path)

    _LOGGER.error("Unable to find component %s", comp_name)

    return None


class Components:
    """Helper to load components."""

    def __init__(self, hass):
        """Initialize the Components class."""
        self._hass = hass

    def __getattr__(self, comp_name):
        """Fetch a component."""
        component = get_component(comp_name)
        if component is None:
            raise ImportError('Unable to load {}'.format(comp_name))
        wrapped = ModuleWrapper(self._hass, component)
        setattr(self, comp_name, wrapped)
        return wrapped


class Helpers:
    """Helper to load helpers."""

    def __init__(self, hass):
        """Initialize the Helpers class."""
        self._hass = hass

    def __getattr__(self, helper_name):
        """Fetch a helper."""
        helper = importlib.import_module(
            'homeassistant.helpers.{}'.format(helper_name))
        wrapped = ModuleWrapper(self._hass, helper)
        setattr(self, helper_name, wrapped)
        return wrapped


class ModuleWrapper:
    """Class to wrap a Python module and auto fill in hass argument."""

    def __init__(self, hass, module):
        """Initialize the module wrapper."""
        self._hass = hass
        self._module = module

    def __getattr__(self, attr):
        """Fetch an attribute."""
        value = getattr(self._module, attr)

        if hasattr(value, '__bind_hass'):
            value = ft.partial(value, self._hass)

        setattr(self, attr, value)
        return value


def bind_hass(func):
    """Decorate function to indicate that first argument is hass."""
    # pylint: disable=protected-access
    func.__bind_hass = True
    return func


def load_order_component(comp_name: str) -> OrderedSet:
    """Return an OrderedSet of components in the correct order of loading.

    Raises HomeAssistantError if a circular dependency is detected.
    Returns an empty list if component could not be loaded.

    Async friendly.
    """
    return _load_order_component(comp_name, OrderedSet(), set())


def _load_order_component(comp_name: str, load_order: OrderedSet,
                          loading: Set) -> OrderedSet:
    """Recursive function to get load order of components.

    Async friendly.
    """
    component = get_component(comp_name)

    # If None it does not exist, error already thrown by get_component.
    if component is None:
        return OrderedSet()

    loading.add(comp_name)

    for dependency in getattr(component, 'DEPENDENCIES', []):
        # Check not already loaded
        if dependency in load_order:
            continue

        # If we are already loading it, we have a circular dependency.
        if dependency in loading:
            _LOGGER.error("Circular dependency detected: %s -> %s",
                          comp_name, dependency)
            return OrderedSet()

        dep_load_order = _load_order_component(dependency, load_order, loading)

        # length == 0 means error loading dependency or children
        if not dep_load_order:
            _LOGGER.error("Error loading %s dependency: %s",
                          comp_name, dependency)
            return OrderedSet()

        load_order.update(dep_load_order)

    load_order.add(comp_name)
    loading.remove(comp_name)

    return load_order


def _check_prepared() -> None:
    """Issue a warning if loader.prepare() has never been called.

    Async friendly.
    """
    if not PREPARED:
        _LOGGER.warning((
            "You did not call loader.prepare() yet. "
            "Certain functionality might not be working"))
