"""
The methods for loading Home Assistant integrations.

This module has quite some complex parts. I have tried to add as much
documentation as possible to keep it understandable.
"""
import asyncio
import functools as ft
import importlib
import json
import logging
import pathlib
import sys
from types import ModuleType
from typing import (
    Optional,
    Set,
    TYPE_CHECKING,
    Callable,
    Any,
    TypeVar,
    List,
    Dict,
    Union,
    cast,
)

# Typing imports that create a circular dependency
# pylint: disable=using-constant-test,unused-import
if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant  # noqa

CALLABLE_T = TypeVar('CALLABLE_T', bound=Callable)  # noqa pylint: disable=invalid-name

DEPENDENCY_BLACKLIST = {'config'}

_LOGGER = logging.getLogger(__name__)


DATA_COMPONENTS = 'components'
DATA_INTEGRATIONS = 'integrations'
PACKAGE_CUSTOM_COMPONENTS = 'custom_components'
PACKAGE_BUILTIN = 'homeassistant.components'
LOOKUP_PATHS = [PACKAGE_CUSTOM_COMPONENTS, PACKAGE_BUILTIN]
CUSTOM_WARNING = (
    'You are using a custom integration for %s which has not '
    'been tested by Home Assistant. This component might '
    'cause stability problems, be sure to disable it if you '
    'do experience issues with Home Assistant.'
)
_UNDEF = object()


def manifest_from_legacy_module(domain: str, module: ModuleType) -> Dict:
    """Generate a manifest from a legacy module."""
    return {
        'domain': domain,
        'name': domain,
        'documentation': None,
        'requirements': getattr(module, 'REQUIREMENTS', []),
        'dependencies': getattr(module, 'DEPENDENCIES', []),
        'codeowners': [],
    }


class Integration:
    """An integration in Home Assistant."""

    @classmethod
    def resolve_from_root(cls, hass: 'HomeAssistant', root_module: ModuleType,
                          domain: str) -> 'Optional[Integration]':
        """Resolve an integration from a root module."""
        for base in root_module.__path__:   # type: ignore
            manifest_path = (
                pathlib.Path(base) / domain / 'manifest.json'
            )

            if not manifest_path.is_file():
                continue

            try:
                manifest = json.loads(manifest_path.read_text())
            except ValueError as err:
                _LOGGER.error("Error parsing manifest.json file at %s: %s",
                              manifest_path, err)
                continue

            return cls(
                hass, "{}.{}".format(root_module.__name__, domain),
                manifest_path.parent, manifest
            )

        return None

    @classmethod
    def resolve_legacy(cls, hass: 'HomeAssistant', domain: str) \
            -> 'Optional[Integration]':
        """Resolve legacy component.

        Will create a stub manifest.
        """
        comp = _load_file(hass, domain, LOOKUP_PATHS)

        if comp is None:
            return None

        return cls(
            hass, comp.__name__, pathlib.Path(comp.__file__).parent,
            manifest_from_legacy_module(domain, comp)
        )

    def __init__(self, hass: 'HomeAssistant', pkg_path: str,
                 file_path: pathlib.Path, manifest: Dict):
        """Initialize an integration."""
        self.hass = hass
        self.pkg_path = pkg_path
        self.file_path = file_path
        self.name = manifest['name']  # type: str
        self.domain = manifest['domain']  # type: str
        self.dependencies = manifest['dependencies']  # type: List[str]
        self.after_dependencies = manifest.get(
            'after_dependencies')  # type: Optional[List[str]]
        self.requirements = manifest['requirements']  # type: List[str]
        _LOGGER.info("Loaded %s from %s", self.domain, pkg_path)

    def get_component(self) -> ModuleType:
        """Return the component."""
        cache = self.hass.data.setdefault(DATA_COMPONENTS, {})
        if self.domain not in cache:
            cache[self.domain] = importlib.import_module(self.pkg_path)
        return cache[self.domain]  # type: ignore

    def get_platform(self, platform_name: str) -> ModuleType:
        """Return a platform for an integration."""
        cache = self.hass.data.setdefault(DATA_COMPONENTS, {})
        full_name = "{}.{}".format(self.domain, platform_name)
        if full_name not in cache:
            cache[full_name] = importlib.import_module(
                "{}.{}".format(self.pkg_path, platform_name)
            )
        return cache[full_name]  # type: ignore

    def __repr__(self) -> str:
        """Text representation of class."""
        return "<Integration {}: {}>".format(self.domain, self.pkg_path)


async def async_get_integration(hass: 'HomeAssistant', domain: str)\
         -> Integration:
    """Get an integration."""
    cache = hass.data.get(DATA_INTEGRATIONS)
    if cache is None:
        if not _async_mount_config_dir(hass):
            raise IntegrationNotFound(domain)
        cache = hass.data[DATA_INTEGRATIONS] = {}

    int_or_evt = cache.get(
        domain, _UNDEF)  # type: Optional[Union[Integration, asyncio.Event]]

    if isinstance(int_or_evt, asyncio.Event):
        await int_or_evt.wait()
        int_or_evt = cache.get(domain, _UNDEF)

        # When we have waited and it's _UNDEF, it doesn't exist
        # We don't cache that it doesn't exist, or else people can't fix it
        # and then restart, because their config will never be valid.
        if int_or_evt is _UNDEF:
            raise IntegrationNotFound(domain)

    if int_or_evt is not _UNDEF:
        return cast(Integration, int_or_evt)

    event = cache[domain] = asyncio.Event()

    try:
        import custom_components
        integration = await hass.async_add_executor_job(
            Integration.resolve_from_root, hass, custom_components, domain
        )
        if integration is not None:
            _LOGGER.warning(CUSTOM_WARNING, domain)
            cache[domain] = integration
            event.set()
            return integration

    except ImportError:
        # Import error if "custom_components" doesn't exist
        pass

    from homeassistant import components

    integration = await hass.async_add_executor_job(
        Integration.resolve_from_root, hass, components, domain
    )

    if integration is not None:
        cache[domain] = integration
        event.set()
        return integration

    integration = Integration.resolve_legacy(hass, domain)
    if integration is not None:
        cache[domain] = integration
    else:
        # Remove event from cache.
        cache.pop(domain)

    event.set()

    if not integration:
        raise IntegrationNotFound(domain)

    return integration


class LoaderError(Exception):
    """Loader base error."""


class IntegrationNotFound(LoaderError):
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


def _load_file(hass,  # type: HomeAssistant
               comp_or_platform: str,
               base_paths: List[str]) -> Optional[ModuleType]:
    """Try to load specified file.

    Looks in config dir first, then built-in components.
    Only returns it if also found to be valid.
    Async friendly.
    """
    try:
        return hass.data[DATA_COMPONENTS][comp_or_platform]  # type: ignore
    except KeyError:
        pass

    cache = hass.data.get(DATA_COMPONENTS)
    if cache is None:
        if not _async_mount_config_dir(hass):
            return None
        cache = hass.data[DATA_COMPONENTS] = {}

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

            cache[comp_or_platform] = module

            if module.__name__.startswith(PACKAGE_CUSTOM_COMPONENTS):
                _LOGGER.warning(CUSTOM_WARNING, comp_or_platform)

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
        # Test integration cache
        integration = self._hass.data.get(DATA_INTEGRATIONS, {}).get(comp_name)

        if isinstance(integration, Integration):
            component = integration.get_component(
            )  # type: Optional[ModuleType]
        else:
            # Fallback to importing old-school
            component = _load_file(self._hass, comp_name, LOOKUP_PATHS)

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


async def async_component_dependencies(hass,  # type: HomeAssistant
                                       domain: str) -> Set[str]:
    """Return all dependencies and subdependencies of components.

    Raises CircularDependency if a circular dependency is found.
    """
    return await _async_component_dependencies(hass, domain, set(), set())


async def _async_component_dependencies(hass,  # type: HomeAssistant
                                        domain: str, loaded: Set[str],
                                        loading: Set) -> Set[str]:
    """Recursive function to get component dependencies.

    Async friendly.
    """
    integration = await async_get_integration(hass, domain)

    loading.add(domain)

    for dependency_domain in integration.dependencies:
        # Check not already loaded
        if dependency_domain in loaded:
            continue

        # If we are already loading it, we have a circular dependency.
        if dependency_domain in loading:
            raise CircularDependency(domain, dependency_domain)

        dep_loaded = await _async_component_dependencies(
            hass, dependency_domain, loaded, loading)

        loaded.update(dep_loaded)

    loaded.add(domain)
    loading.remove(domain)

    return loaded


def _async_mount_config_dir(hass,  # type: HomeAssistant
                            ) -> bool:
    """Mount config dir in order to load custom_component.

    Async friendly but not a coroutine.
    """
    if hass.config.config_dir is None:
        _LOGGER.error("Can't load components - config dir is not set")
        return False
    if hass.config.config_dir not in sys.path:
        sys.path.insert(0, hass.config.config_dir)
    return True
