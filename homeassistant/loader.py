"""
The methods for loading Home Assistant integrations.

This module has quite some complex parts. I have tried to add as much
documentation as possible to keep it understandable.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
import functools as ft
import importlib
import json
import logging
import pathlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Dict, TypedDict, TypeVar, cast

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionException,
    AwesomeVersionStrategy,
)

from homeassistant.generated.dhcp import DHCP
from homeassistant.generated.mqtt import MQTT
from homeassistant.generated.ssdp import SSDP
from homeassistant.generated.zeroconf import HOMEKIT, ZEROCONF
from homeassistant.util.async_ import gather_with_concurrency

# Typing imports that create a circular dependency
if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# mypy: disallow-any-generics

CALLABLE_T = TypeVar(  # pylint: disable=invalid-name
    "CALLABLE_T", bound=Callable[..., Any]
)

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENTS = "components"
DATA_INTEGRATIONS = "integrations"
DATA_CUSTOM_COMPONENTS = "custom_components"
PACKAGE_CUSTOM_COMPONENTS = "custom_components"
PACKAGE_BUILTIN = "homeassistant.components"
CUSTOM_WARNING = (
    "We found a custom integration %s which has not "
    "been tested by Home Assistant. This component might "
    "cause stability problems, be sure to disable it if you "
    "experience issues with Home Assistant"
)

_UNDEF = object()  # Internal; not helpers.typing.UNDEFINED due to circular dependency

MAX_LOAD_CONCURRENTLY = 4


class Manifest(TypedDict, total=False):
    """
    Integration manifest.

    Note that none of the attributes are marked Optional here. However, some of them may be optional in manifest.json
    in the sense that they can be omitted altogether. But when present, they should not have null values in it.
    """

    name: str
    disabled: str
    domain: str
    dependencies: list[str]
    after_dependencies: list[str]
    requirements: list[str]
    config_flow: bool
    documentation: str
    issue_tracker: str
    quality_scale: str
    iot_class: str
    mqtt: list[str]
    ssdp: list[dict[str, str]]
    zeroconf: list[str | dict[str, str]]
    dhcp: list[dict[str, str]]
    homekit: dict[str, list[str]]
    is_built_in: bool
    version: str
    codeowners: list[str]


def manifest_from_legacy_module(domain: str, module: ModuleType) -> Manifest:
    """Generate a manifest from a legacy module."""
    return {
        "domain": domain,
        "name": domain,
        "requirements": getattr(module, "REQUIREMENTS", []),
        "dependencies": getattr(module, "DEPENDENCIES", []),
        "codeowners": [],
    }


async def _async_get_custom_components(
    hass: HomeAssistant,
) -> dict[str, Integration]:
    """Return list of custom integrations."""
    if hass.config.safe_mode:
        return {}

    try:
        import custom_components  # pylint: disable=import-outside-toplevel
    except ImportError:
        return {}

    def get_sub_directories(paths: list[str]) -> list[pathlib.Path]:
        """Return all sub directories in a set of paths."""
        return [
            entry
            for path in paths
            for entry in pathlib.Path(path).iterdir()
            if entry.is_dir()
        ]

    dirs = await hass.async_add_executor_job(
        get_sub_directories, custom_components.__path__
    )

    integrations = await gather_with_concurrency(
        MAX_LOAD_CONCURRENTLY,
        *(
            hass.async_add_executor_job(
                Integration.resolve_from_root, hass, custom_components, comp.name
            )
            for comp in dirs
        ),
    )

    return {
        integration.domain: integration
        for integration in integrations
        if integration is not None
    }


async def async_get_custom_components(
    hass: HomeAssistant,
) -> dict[str, Integration]:
    """Return cached list of custom integrations."""
    reg_or_evt = hass.data.get(DATA_CUSTOM_COMPONENTS)

    if reg_or_evt is None:
        evt = hass.data[DATA_CUSTOM_COMPONENTS] = asyncio.Event()

        reg = await _async_get_custom_components(hass)

        hass.data[DATA_CUSTOM_COMPONENTS] = reg
        evt.set()
        return reg

    if isinstance(reg_or_evt, asyncio.Event):
        await reg_or_evt.wait()
        return cast(Dict[str, "Integration"], hass.data.get(DATA_CUSTOM_COMPONENTS))

    return cast(Dict[str, "Integration"], reg_or_evt)


async def async_get_config_flows(hass: HomeAssistant) -> set[str]:
    """Return cached list of config flows."""
    # pylint: disable=import-outside-toplevel
    from homeassistant.generated.config_flows import FLOWS

    flows: set[str] = set()
    flows.update(FLOWS)

    integrations = await async_get_custom_components(hass)
    flows.update(
        [
            integration.domain
            for integration in integrations.values()
            if integration.config_flow
        ]
    )

    return flows


async def async_get_zeroconf(hass: HomeAssistant) -> dict[str, list[dict[str, str]]]:
    """Return cached list of zeroconf types."""
    zeroconf: dict[str, list[dict[str, str]]] = ZEROCONF.copy()

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.zeroconf:
            continue
        for entry in integration.zeroconf:
            data = {"domain": integration.domain}
            if isinstance(entry, dict):
                typ = entry["type"]
                entry_without_type = entry.copy()
                del entry_without_type["type"]
                data.update(entry_without_type)
            else:
                typ = entry

            zeroconf.setdefault(typ, []).append(data)

    return zeroconf


async def async_get_dhcp(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return cached list of dhcp types."""
    dhcp: list[dict[str, str]] = DHCP.copy()

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.dhcp:
            continue
        for entry in integration.dhcp:
            dhcp.append({"domain": integration.domain, **entry})

    return dhcp


async def async_get_homekit(hass: HomeAssistant) -> dict[str, str]:
    """Return cached list of homekit models."""

    homekit: dict[str, str] = HOMEKIT.copy()

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if (
            not integration.homekit
            or "models" not in integration.homekit
            or not integration.homekit["models"]
        ):
            continue
        for model in integration.homekit["models"]:
            homekit[model] = integration.domain

    return homekit


async def async_get_ssdp(hass: HomeAssistant) -> dict[str, list[dict[str, str]]]:
    """Return cached list of ssdp mappings."""

    ssdp: dict[str, list[dict[str, str]]] = SSDP.copy()

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.ssdp:
            continue

        ssdp[integration.domain] = integration.ssdp

    return ssdp


async def async_get_mqtt(hass: HomeAssistant) -> dict[str, list[str]]:
    """Return cached list of MQTT mappings."""

    mqtt: dict[str, list[str]] = MQTT.copy()

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.mqtt:
            continue

        mqtt[integration.domain] = integration.mqtt

    return mqtt


class Integration:
    """An integration in Home Assistant."""

    @classmethod
    def resolve_from_root(
        cls, hass: HomeAssistant, root_module: ModuleType, domain: str
    ) -> Integration | None:
        """Resolve an integration from a root module."""
        for base in root_module.__path__:  # type: ignore
            manifest_path = pathlib.Path(base) / domain / "manifest.json"

            if not manifest_path.is_file():
                continue

            try:
                manifest = json.loads(manifest_path.read_text())
            except ValueError as err:
                _LOGGER.error(
                    "Error parsing manifest.json file at %s: %s", manifest_path, err
                )
                continue

            integration = cls(
                hass,
                f"{root_module.__name__}.{domain}",
                manifest_path.parent,
                manifest,
            )

            if integration.is_built_in:
                return integration

            _LOGGER.warning(CUSTOM_WARNING, integration.domain)
            try:
                AwesomeVersion(
                    integration.version,
                    [
                        AwesomeVersionStrategy.CALVER,
                        AwesomeVersionStrategy.SEMVER,
                        AwesomeVersionStrategy.SIMPLEVER,
                        AwesomeVersionStrategy.BUILDVER,
                        AwesomeVersionStrategy.PEP440,
                    ],
                )
            except AwesomeVersionException:
                _LOGGER.error(
                    "The custom integration '%s' does not have a "
                    "valid version key (%s) in the manifest file and was blocked from loading. "
                    "See https://developers.home-assistant.io/blog/2021/01/29/custom-integration-changes#versions for more details",
                    integration.domain,
                    integration.version,
                )
                return None
            return integration

        return None

    def __init__(
        self,
        hass: HomeAssistant,
        pkg_path: str,
        file_path: pathlib.Path,
        manifest: Manifest,
    ) -> None:
        """Initialize an integration."""
        self.hass = hass
        self.pkg_path = pkg_path
        self.file_path = file_path
        self.manifest = manifest
        manifest["is_built_in"] = self.is_built_in

        if self.dependencies:
            self._all_dependencies_resolved: bool | None = None
            self._all_dependencies: set[str] | None = None
        else:
            self._all_dependencies_resolved = True
            self._all_dependencies = set()

        _LOGGER.info("Loaded %s from %s", self.domain, pkg_path)

    @property
    def name(self) -> str:
        """Return name."""
        return self.manifest["name"]

    @property
    def disabled(self) -> str | None:
        """Return reason integration is disabled."""
        return self.manifest.get("disabled")

    @property
    def domain(self) -> str:
        """Return domain."""
        return self.manifest["domain"]

    @property
    def dependencies(self) -> list[str]:
        """Return dependencies."""
        return self.manifest.get("dependencies", [])

    @property
    def after_dependencies(self) -> list[str]:
        """Return after_dependencies."""
        return self.manifest.get("after_dependencies", [])

    @property
    def requirements(self) -> list[str]:
        """Return requirements."""
        return self.manifest.get("requirements", [])

    @property
    def config_flow(self) -> bool:
        """Return config_flow."""
        return self.manifest.get("config_flow") or False

    @property
    def documentation(self) -> str | None:
        """Return documentation."""
        return self.manifest.get("documentation")

    @property
    def issue_tracker(self) -> str | None:
        """Return issue tracker link."""
        return self.manifest.get("issue_tracker")

    @property
    def quality_scale(self) -> str | None:
        """Return Integration Quality Scale."""
        return self.manifest.get("quality_scale")

    @property
    def iot_class(self) -> str | None:
        """Return the integration IoT Class."""
        return self.manifest.get("iot_class")

    @property
    def mqtt(self) -> list[str] | None:
        """Return Integration MQTT entries."""
        return self.manifest.get("mqtt")

    @property
    def ssdp(self) -> list[dict[str, str]] | None:
        """Return Integration SSDP entries."""
        return self.manifest.get("ssdp")

    @property
    def zeroconf(self) -> list[str | dict[str, str]] | None:
        """Return Integration zeroconf entries."""
        return self.manifest.get("zeroconf")

    @property
    def dhcp(self) -> list[dict[str, str]] | None:
        """Return Integration dhcp entries."""
        return self.manifest.get("dhcp")

    @property
    def homekit(self) -> dict[str, list[str]] | None:
        """Return Integration homekit entries."""
        return self.manifest.get("homekit")

    @property
    def is_built_in(self) -> bool:
        """Test if package is a built-in integration."""
        return self.pkg_path.startswith(PACKAGE_BUILTIN)

    @property
    def version(self) -> AwesomeVersion | None:
        """Return the version of the integration."""
        if "version" not in self.manifest:
            return None
        return AwesomeVersion(self.manifest["version"])

    @property
    def all_dependencies(self) -> set[str]:
        """Return all dependencies including sub-dependencies."""
        if self._all_dependencies is None:
            raise RuntimeError("Dependencies not resolved!")

        return self._all_dependencies

    @property
    def all_dependencies_resolved(self) -> bool:
        """Return if all dependencies have been resolved."""
        return self._all_dependencies_resolved is not None

    async def resolve_dependencies(self) -> bool:
        """Resolve all dependencies."""
        if self._all_dependencies_resolved is not None:
            return self._all_dependencies_resolved

        try:
            dependencies = await _async_component_dependencies(
                self.hass, self.domain, self, set(), set()
            )
            dependencies.discard(self.domain)
            self._all_dependencies = dependencies
            self._all_dependencies_resolved = True
        except IntegrationNotFound as err:
            _LOGGER.error(
                "Unable to resolve dependencies for %s:  we are unable to resolve (sub)dependency %s",
                self.domain,
                err.domain,
            )
            self._all_dependencies_resolved = False
        except CircularDependency as err:
            _LOGGER.error(
                "Unable to resolve dependencies for %s:  it contains a circular dependency: %s -> %s",
                self.domain,
                err.from_domain,
                err.to_domain,
            )
            self._all_dependencies_resolved = False

        return self._all_dependencies_resolved

    def get_component(self) -> ModuleType:
        """Return the component."""
        cache = self.hass.data.setdefault(DATA_COMPONENTS, {})
        if self.domain not in cache:
            cache[self.domain] = importlib.import_module(self.pkg_path)
        return cache[self.domain]  # type: ignore

    def get_platform(self, platform_name: str) -> ModuleType:
        """Return a platform for an integration."""
        cache = self.hass.data.setdefault(DATA_COMPONENTS, {})
        full_name = f"{self.domain}.{platform_name}"
        if full_name not in cache:
            cache[full_name] = self._import_platform(platform_name)
        return cache[full_name]  # type: ignore

    def _import_platform(self, platform_name: str) -> ModuleType:
        """Import the platform."""
        return importlib.import_module(f"{self.pkg_path}.{platform_name}")

    def __repr__(self) -> str:
        """Text representation of class."""
        return f"<Integration {self.domain}: {self.pkg_path}>"


async def async_get_integration(hass: HomeAssistant, domain: str) -> Integration:
    """Get an integration."""
    cache = hass.data.get(DATA_INTEGRATIONS)
    if cache is None:
        if not _async_mount_config_dir(hass):
            raise IntegrationNotFound(domain)
        cache = hass.data[DATA_INTEGRATIONS] = {}

    int_or_evt: Integration | asyncio.Event | None = cache.get(domain, _UNDEF)

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
        integration = await _async_get_integration(hass, domain)
    except Exception:
        # Remove event from cache.
        cache.pop(domain)
        event.set()
        raise

    cache[domain] = integration
    event.set()
    return integration


async def _async_get_integration(hass: HomeAssistant, domain: str) -> Integration:
    # Instead of using resolve_from_root we use the cache of custom
    # components to find the integration.
    if integration := (await async_get_custom_components(hass)).get(domain):
        return integration

    from homeassistant import components  # pylint: disable=import-outside-toplevel

    if integration := await hass.async_add_executor_job(
        Integration.resolve_from_root, hass, components, domain
    ):
        return integration

    raise IntegrationNotFound(domain)


class LoaderError(Exception):
    """Loader base error."""


class IntegrationNotFound(LoaderError):
    """Raised when a component is not found."""

    def __init__(self, domain: str) -> None:
        """Initialize a component not found error."""
        super().__init__(f"Integration '{domain}' not found.")
        self.domain = domain


class CircularDependency(LoaderError):
    """Raised when a circular dependency is found when resolving components."""

    def __init__(self, from_domain: str, to_domain: str) -> None:
        """Initialize circular dependency error."""
        super().__init__(f"Circular dependency detected: {from_domain} -> {to_domain}.")
        self.from_domain = from_domain
        self.to_domain = to_domain


def _load_file(
    hass: HomeAssistant, comp_or_platform: str, base_paths: list[str]
) -> ModuleType | None:
    """Try to load specified file.

    Looks in config dir first, then built-in components.
    Only returns it if also found to be valid.
    Async friendly.
    """
    with suppress(KeyError):
        return hass.data[DATA_COMPONENTS][comp_or_platform]  # type: ignore

    cache = hass.data.get(DATA_COMPONENTS)
    if cache is None:
        if not _async_mount_config_dir(hass):
            return None
        cache = hass.data[DATA_COMPONENTS] = {}

    for path in (f"{base}.{comp_or_platform}" for base in base_paths):
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
            if getattr(module, "__file__", None) is None:
                continue

            cache[comp_or_platform] = module

            return module

        except ImportError as err:
            # This error happens if for example custom_components/switch
            # exists and we try to load switch.demo.
            # Ignore errors for custom_components, custom_components.switch
            # and custom_components.switch.demo.
            white_listed_errors = []
            parts = []
            for part in path.split("."):
                parts.append(part)
                white_listed_errors.append(f"No module named '{'.'.join(parts)}'")

            if str(err) not in white_listed_errors:
                _LOGGER.exception(
                    ("Error loading %s. Make sure all dependencies are installed"), path
                )

    return None


class ModuleWrapper:
    """Class to wrap a Python module and auto fill in hass argument."""

    def __init__(self, hass: HomeAssistant, module: ModuleType) -> None:
        """Initialize the module wrapper."""
        self._hass = hass
        self._module = module

    def __getattr__(self, attr: str) -> Any:
        """Fetch an attribute."""
        value = getattr(self._module, attr)

        if hasattr(value, "__bind_hass"):
            value = ft.partial(value, self._hass)

        setattr(self, attr, value)
        return value


class Components:
    """Helper to load components."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Components class."""
        self._hass = hass

    def __getattr__(self, comp_name: str) -> ModuleWrapper:
        """Fetch a component."""
        # Test integration cache
        integration = self._hass.data.get(DATA_INTEGRATIONS, {}).get(comp_name)

        if isinstance(integration, Integration):
            component: ModuleType | None = integration.get_component()
        else:
            # Fallback to importing old-school
            component = _load_file(self._hass, comp_name, _lookup_path(self._hass))

        if component is None:
            raise ImportError(f"Unable to load {comp_name}")

        wrapped = ModuleWrapper(self._hass, component)
        setattr(self, comp_name, wrapped)
        return wrapped


class Helpers:
    """Helper to load helpers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Helpers class."""
        self._hass = hass

    def __getattr__(self, helper_name: str) -> ModuleWrapper:
        """Fetch a helper."""
        helper = importlib.import_module(f"homeassistant.helpers.{helper_name}")
        wrapped = ModuleWrapper(self._hass, helper)
        setattr(self, helper_name, wrapped)
        return wrapped


def bind_hass(func: CALLABLE_T) -> CALLABLE_T:
    """Decorate function to indicate that first argument is hass."""
    setattr(func, "__bind_hass", True)
    return func


async def _async_component_dependencies(
    hass: HomeAssistant,
    start_domain: str,
    integration: Integration,
    loaded: set[str],
    loading: set[str],
) -> set[str]:
    """Recursive function to get component dependencies.

    Async friendly.
    """
    domain = integration.domain
    loading.add(domain)

    for dependency_domain in integration.dependencies:
        # Check not already loaded
        if dependency_domain in loaded:
            continue

        # If we are already loading it, we have a circular dependency.
        if dependency_domain in loading:
            raise CircularDependency(domain, dependency_domain)

        loaded.add(dependency_domain)

        dep_integration = await async_get_integration(hass, dependency_domain)

        if start_domain in dep_integration.after_dependencies:
            raise CircularDependency(start_domain, dependency_domain)

        if dep_integration.dependencies:
            dep_loaded = await _async_component_dependencies(
                hass, start_domain, dep_integration, loaded, loading
            )

            loaded.update(dep_loaded)

    loaded.add(domain)
    loading.remove(domain)

    return loaded


def _async_mount_config_dir(hass: HomeAssistant) -> bool:
    """Mount config dir in order to load custom_component.

    Async friendly but not a coroutine.
    """
    if hass.config.config_dir is None:
        _LOGGER.error("Can't load integrations - configuration directory is not set")
        return False
    if hass.config.config_dir not in sys.path:
        sys.path.insert(0, hass.config.config_dir)
    return True


def _lookup_path(hass: HomeAssistant) -> list[str]:
    """Return the lookup paths for legacy lookups."""
    if hass.config.safe_mode:
        return [PACKAGE_BUILTIN]
    return [PACKAGE_CUSTOM_COMPONENTS, PACKAGE_BUILTIN]
