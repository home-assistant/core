"""
The methods for loading Home Assistant components.

This module has quite some complex parts. I have tried to add as much
documentation as possible to keep it understandable.

Components can be accessed via hass.components.switch from your code.
If you want to retrieve a platform that is part of a component, you should
call get_component(hass, 'switch.your_platform'). In both cases the config
directory is checked to see if it contains a user provided version. If not
available it will check the built-in components and platforms.
"""
import functools as ft
import importlib
import logging
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


DATA_KEY = 'components'
PATH_CUSTOM_COMPONENTS = 'custom_components'
PACKAGE_COMPONENTS = 'homeassistant.components'


def set_component(hass, comp_name: str, component: ModuleType) -> None:
    """Set a component in the cache.

    Async friendly.
    """
    cache = hass.data.get(DATA_KEY)
    if cache is None:
        cache = hass.data[DATA_KEY] = {}
    cache[comp_name] = component


def get_platform(hass, domain: str, platform: str) -> Optional[ModuleType]:
    """Try to load specified platform.

    Async friendly.
    """
    return get_component(hass, PLATFORM_FORMAT.format(domain, platform))


def get_component(hass, comp_or_platform):
    """Load a module from either custom component or built-in."""
    try:
        return hass.data[DATA_KEY][comp_or_platform]
    except KeyError:
        pass

    # Try custom component
    module = _load_module(hass.config.path(PATH_CUSTOM_COMPONENTS),
                          comp_or_platform)

    if module is None:
        try:
            module = importlib.import_module(
                '{}.{}'.format(PACKAGE_COMPONENTS, comp_or_platform))
        except ImportError:
            module = None

    cache = hass.data.get(DATA_KEY)
    if cache is None:
        cache = hass.data[DATA_KEY] = {}
    cache[comp_or_platform] = module

    return module


def _find_spec(path, name):
    for finder in sys.meta_path:
        try:
            spec = finder.find_spec(name, path=path)
            if spec is not None:
                return spec
        except AttributeError:
            # Not all finders have the find_spec method
            pass
    return None


def _load_module(path, name):
    """Load a module based on a folder and a name."""
    spec = _find_spec([path], name)

    # Special handling if loading platforms and the folder is a namespace
    # (namespace is a folder without __init__.py)
    if spec is None and '.' in name:
        parent_spec = _find_spec([path], name.split('.')[0])
        if (parent_spec is None or
                parent_spec.submodule_search_locations is None):
            return None
        spec = _find_spec(parent_spec.submodule_search_locations, name)

    # Not found
    if spec is None:
        return None

    # This is a namespace
    if spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Components:
    """Helper to load components."""

    def __init__(self, hass):
        """Initialize the Components class."""
        self._hass = hass

    def __getattr__(self, comp_name):
        """Fetch a component."""
        component = get_component(self._hass, comp_name)
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


def load_order_component(hass, comp_name: str) -> OrderedSet:
    """Return an OrderedSet of components in the correct order of loading.

    Raises HomeAssistantError if a circular dependency is detected.
    Returns an empty list if component could not be loaded.

    Async friendly.
    """
    return _load_order_component(hass, comp_name, OrderedSet(), set())


def _load_order_component(hass, comp_name: str, load_order: OrderedSet,
                          loading: Set) -> OrderedSet:
    """Recursive function to get load order of components.

    Async friendly.
    """
    component = get_component(hass, comp_name)

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

        dep_load_order = _load_order_component(
            hass, dependency, load_order, loading)

        # length == 0 means error loading dependency or children
        if not dep_load_order:
            _LOGGER.error("Error loading %s dependency: %s",
                          comp_name, dependency)
            return OrderedSet()

        load_order.update(dep_load_order)

    load_order.add(comp_name)
    loading.remove(comp_name)

    return load_order
