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
from typing import Optional, Set, TYPE_CHECKING, Callable, Any, TypeVar, List  # noqa pylint: disable=unused-import

from homeassistant.const import PLATFORM_FORMAT

# Typing imports that create a circular dependency
# pylint: disable=using-constant-test,unused-import
if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant  # NOQA

CALLABLE_T = TypeVar('CALLABLE_T', bound=Callable)  # noqa pylint: disable=invalid-name

PREPARED = False

DEPENDENCY_BLACKLIST = {'config'}

_LOGGER = logging.getLogger(__name__)


DATA_KEY = 'components'
PACKAGE_CUSTOM_COMPONENTS = 'custom_components'
PACKAGE_BUILTIN = 'homeassistant.components'
PACKAGE_AIS_DOM = 'homeassistant.ais_dom'
LOOKUP_PATHS = [PACKAGE_AIS_DOM, PACKAGE_CUSTOM_COMPONENTS, PACKAGE_BUILTIN]
COMPONENTS_WITH_BAD_PLATFORMS = ['automation', 'mqtt', 'telegram_bot']


class LoaderError(Exception):
    """Loader base error."""


class ComponentNotFound(LoaderError):
    """Raised when a component is not found."""

    def __init__(self, domain: str) -> None:
        """Initialize a component not found error."""
        super().__init__("Component {} not found.".format(domain))
        self.domain = domain


class CircularDependency(LoaderError):
    """Raised when a circular dependency is found when resolving components."""

    def __init__(self, from_domain: str, to_domain: str) -> None:
        """Initialize circular dependency error."""
        super().__init__("Circular dependency detected: {} -> {}.".format(
            from_domain, to_domain))
        self.from_domain = from_domain
        self.to_domain = to_domain


def set_component(hass,  # type: HomeAssistant
                  comp_name: str, component: Optional[ModuleType]) -> None:
    """Set a component in the cache.

    Async friendly.
    """
    cache = hass.data.setdefault(DATA_KEY, {})
    cache[comp_name] = component


def get_platform(hass,  # type: HomeAssistant
                 domain: str, platform_name: str) -> Optional[ModuleType]:
    """Try to load specified platform.

    Example invocation: get_platform(hass, 'light', 'hue')

    Async friendly.
    """
    # If the platform has a component, we will limit the platform loading path
    # to be the same source (custom/built-in).
    if domain not in COMPONENTS_WITH_BAD_PLATFORMS:
        component = _load_file(hass, platform_name, LOOKUP_PATHS)
    else:
        # avoid load component for legacy platform
        component = None

    # Until we have moved all platforms under their component/own folder, it
    # can be that the component is None.
    if component is not None:
        base_paths = [component.__name__.rsplit('.', 1)[0]]
    else:
        base_paths = LOOKUP_PATHS

    platform = _load_file(
        hass, PLATFORM_FORMAT.format(domain=domain, platform=platform_name),
        base_paths)

    if platform is not None:
        return platform

    # Legacy platform check for automation: components/automation/event.py
    if component is None and domain in COMPONENTS_WITH_BAD_PLATFORMS:
        platform = _load_file(
            hass,
            PLATFORM_FORMAT.format(domain=platform_name, platform=domain),
            base_paths
        )

    # Legacy platform check for custom: custom_components/light/hue.py
    # Only check if the component was also in custom components.
    if component is None or base_paths[0] == PACKAGE_CUSTOM_COMPONENTS:
        platform = _load_file(
            hass,
            PLATFORM_FORMAT.format(domain=platform_name, platform=domain),
            [PACKAGE_CUSTOM_COMPONENTS]
        )

    if platform is None:
        if component is None:
            extra = ""
        else:
            extra = " Search path was limited to path of component: {}".format(
                base_paths[0])
        _LOGGER.error("Unable to find platform %s.%s", platform_name, extra)
        return None

    if domain not in COMPONENTS_WITH_BAD_PLATFORMS:
        _LOGGER.error(
            "Integrations need to be in their own folder. Change %s/%s.py to "
            "%s/%s.py. This will stop working soon.",
            domain, platform_name, platform_name, domain)

    return platform


def get_component(hass,  # type: HomeAssistant
                  comp_or_platform: str) -> Optional[ModuleType]:
    """Try to load specified component.

    Async friendly.
    """
    comp = _load_file(hass, comp_or_platform, LOOKUP_PATHS)

    if comp is None:
        _LOGGER.error("Unable to find component %s", comp_or_platform)

    return comp


def _load_file(hass,  # type: HomeAssistant
               comp_or_platform: str,
               base_paths: List[str]) -> Optional[ModuleType]:
    """Try to load specified file.

    Looks in config dir first, then built-in components.
    Only returns it if also found to be valid.
    Async friendly.
    """
    try:
        return hass.data[DATA_KEY][comp_or_platform]  # type: ignore
    except KeyError:
        pass

    cache = hass.data.get(DATA_KEY)
    if cache is None:
        if hass.config.config_dir is None:
            _LOGGER.error("Can't load components - config dir is not set")
            return None
        # Only insert if it's not there (happens during tests)
        if sys.path[0] != hass.config.config_dir:
            sys.path.insert(0, hass.config.config_dir)
        cache = hass.data[DATA_KEY] = {}

    for path in ('{}.{}'.format(base, comp_or_platform)
                 for base in base_paths):
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
            # __file__ was unset for namespaces before Python 3.7
            if getattr(module, '__file__', None) is None:
                continue

            _LOGGER.info("Loaded %s from %s", comp_or_platform, path)

            cache[comp_or_platform] = module

            # if module.__name__.startswith(PACKAGE_CUSTOM_COMPONENTS):
            #     _LOGGER.warning(
            #         'You are using a custom component for %s which has not '
            #         'been tested by Home Assistant. This component might '
            #         'cause stability problems, be sure to disable it if you '
            #         'do experience issues with Home Assistant.',
            #         comp_or_platform)

            return module

        except ImportError as err:
            # This error happens if for example custom_components/switch
            # exists and we try to load switch.demo.
            # Ignore errors for custom_components, custom_components.switch
            # and custom_components.switch.demo.
            white_listed_errors = []
            parts = []
            for part in path.split('.'):
                parts.append(part)
                white_listed_errors.append(
                    "No module named '{}'".format('.'.join(parts)))

            if str(err) not in white_listed_errors:
                _LOGGER.exception(
                    ("Error loading %s. Make sure all "
                     "dependencies are installed"), path)

    return None


class ModuleWrapper:
    """Class to wrap a Python module and auto fill in hass argument."""

    def __init__(self,
                 hass,  # type: HomeAssistant
                 module: ModuleType) -> None:
        """Initialize the module wrapper."""
        self._hass = hass
        self._module = module

    def __getattr__(self, attr: str) -> Any:
        """Fetch an attribute."""
        value = getattr(self._module, attr)

        if hasattr(value, '__bind_hass'):
            value = ft.partial(value, self._hass)

        setattr(self, attr, value)
        return value


class Components:
    """Helper to load components."""

    def __init__(
            self,
            hass  # type: HomeAssistant
    ) -> None:
        """Initialize the Components class."""
        self._hass = hass

    def __getattr__(self, comp_name: str) -> ModuleWrapper:
        """Fetch a component."""
        component = get_component(self._hass, comp_name)
        if component is None:
            raise ImportError('Unable to load {}'.format(comp_name))
        wrapped = ModuleWrapper(self._hass, component)
        setattr(self, comp_name, wrapped)
        return wrapped


class Helpers:
    """Helper to load helpers."""

    def __init__(
            self,
            hass  # type: HomeAssistant
    ) -> None:
        """Initialize the Helpers class."""
        self._hass = hass

    def __getattr__(self, helper_name: str) -> ModuleWrapper:
        """Fetch a helper."""
        helper = importlib.import_module(
            'homeassistant.helpers.{}'.format(helper_name))
        wrapped = ModuleWrapper(self._hass, helper)
        setattr(self, helper_name, wrapped)
        return wrapped


def bind_hass(func: CALLABLE_T) -> CALLABLE_T:
    """Decorate function to indicate that first argument is hass."""
    setattr(func, '__bind_hass', True)
    return func


def component_dependencies(hass,  # type: HomeAssistant
                           comp_name: str) -> Set[str]:
    """Return all dependencies and subdependencies of components.

    Raises CircularDependency if a circular dependency is found.

    Async friendly.
    """
    return _component_dependencies(hass, comp_name, set(), set())


def _component_dependencies(hass,  # type: HomeAssistant
                            comp_name: str, loaded: Set[str],
                            loading: Set) -> Set[str]:
    """Recursive function to get component dependencies.

    Async friendly.
    """
    component = get_component(hass, comp_name)

    if component is None:
        raise ComponentNotFound(comp_name)

    loading.add(comp_name)

    for dependency in getattr(component, 'DEPENDENCIES', []):
        # Check not already loaded
        if dependency in loaded:
            continue

        # If we are already loading it, we have a circular dependency.
        if dependency in loading:
            raise CircularDependency(comp_name, dependency)

        dep_loaded = _component_dependencies(
            hass, dependency, loaded, loading)

        loaded.update(dep_loaded)

    loaded.add(comp_name)
    loading.remove(comp_name)

    return loaded
