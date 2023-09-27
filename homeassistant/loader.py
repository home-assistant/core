"""The methods for loading Home Assistant integrations.

This module has quite some complex parts. I have tried to add as much
documentation as possible to keep it understandable.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
import functools as ft
import importlib
import logging
import pathlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypedDict, TypeVar, cast

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionException,
    AwesomeVersionStrategy,
)
import voluptuous as vol

from . import generated
from .core import HomeAssistant, callback
from .generated.application_credentials import APPLICATION_CREDENTIALS
from .generated.bluetooth import BLUETOOTH
from .generated.dhcp import DHCP
from .generated.mqtt import MQTT
from .generated.ssdp import SSDP
from .generated.usb import USB
from .generated.zeroconf import HOMEKIT, ZEROCONF
from .util.json import JSON_DECODE_EXCEPTIONS, json_loads

# Typing imports that create a circular dependency
if TYPE_CHECKING:
    from .config_entries import ConfigEntry
    from .helpers import device_registry as dr
    from .helpers.typing import ConfigType

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])

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

MOVED_ZEROCONF_PROPS = ("macaddress", "model", "manufacturer")


class DHCPMatcherRequired(TypedDict, total=True):
    """Matcher for the dhcp integration for required fields."""

    domain: str


class DHCPMatcherOptional(TypedDict, total=False):
    """Matcher for the dhcp integration for optional fields."""

    macaddress: str
    hostname: str
    registered_devices: bool


class DHCPMatcher(DHCPMatcherRequired, DHCPMatcherOptional):
    """Matcher for the dhcp integration."""


class BluetoothMatcherRequired(TypedDict, total=True):
    """Matcher for the bluetooth integration for required fields."""

    domain: str


class BluetoothMatcherOptional(TypedDict, total=False):
    """Matcher for the bluetooth integration for optional fields."""

    local_name: str
    service_uuid: str
    service_data_uuid: str
    manufacturer_id: int
    manufacturer_data_start: list[int]
    connectable: bool


class BluetoothMatcher(BluetoothMatcherRequired, BluetoothMatcherOptional):
    """Matcher for the bluetooth integration."""


class USBMatcherRequired(TypedDict, total=True):
    """Matcher for the usb integration for required fields."""

    domain: str


class USBMatcherOptional(TypedDict, total=False):
    """Matcher for the usb integration for optional fields."""

    vid: str
    pid: str
    serial_number: str
    manufacturer: str
    description: str


class USBMatcher(USBMatcherRequired, USBMatcherOptional):
    """Matcher for the bluetooth integration."""


@dataclass(slots=True)
class HomeKitDiscoveredIntegration:
    """HomeKit model."""

    domain: str
    always_discover: bool


class Manifest(TypedDict, total=False):
    """Integration manifest.

    Note that none of the attributes are marked Optional here. However, some of
    them may be optional in manifest.json in the sense that they can be omitted
    altogether. But when present, they should not have null values in it.
    """

    name: str
    disabled: str
    domain: str
    integration_type: Literal[
        "entity", "device", "hardware", "helper", "hub", "service", "system"
    ]
    dependencies: list[str]
    after_dependencies: list[str]
    requirements: list[str]
    config_flow: bool
    documentation: str
    issue_tracker: str
    quality_scale: str
    iot_class: str
    bluetooth: list[dict[str, int | str]]
    mqtt: list[str]
    ssdp: list[dict[str, str]]
    zeroconf: list[str | dict[str, str]]
    dhcp: list[dict[str, bool | str]]
    usb: list[dict[str, str]]
    homekit: dict[str, list[str]]
    is_built_in: bool
    version: str
    codeowners: list[str]
    loggers: list[str]


def async_setup(hass: HomeAssistant) -> None:
    """Set up the necessary data structures."""
    _async_mount_config_dir(hass)
    hass.data[DATA_COMPONENTS] = {}
    hass.data[DATA_INTEGRATIONS] = {}


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

    integrations = await hass.async_add_executor_job(
        _resolve_integrations_from_root,
        hass,
        custom_components,
        [comp.name for comp in dirs],
    )
    return {
        integration.domain: integration
        for integration in integrations.values()
        if integration is not None
    }


async def async_get_custom_components(
    hass: HomeAssistant,
) -> dict[str, Integration]:
    """Return cached list of custom integrations."""
    if (reg_or_evt := hass.data.get(DATA_CUSTOM_COMPONENTS)) is None:
        evt = hass.data[DATA_CUSTOM_COMPONENTS] = asyncio.Event()

        reg = await _async_get_custom_components(hass)

        hass.data[DATA_CUSTOM_COMPONENTS] = reg
        evt.set()
        return reg

    if isinstance(reg_or_evt, asyncio.Event):
        await reg_or_evt.wait()
        return cast(dict[str, "Integration"], hass.data.get(DATA_CUSTOM_COMPONENTS))

    return cast(dict[str, "Integration"], reg_or_evt)


async def async_get_config_flows(
    hass: HomeAssistant,
    type_filter: Literal["device", "helper", "hub", "service"] | None = None,
) -> set[str]:
    """Return cached list of config flows."""
    # pylint: disable-next=import-outside-toplevel
    from .generated.config_flows import FLOWS

    integrations = await async_get_custom_components(hass)
    flows: set[str] = set()

    if type_filter is not None:
        flows.update(FLOWS[type_filter])
    else:
        for type_flows in FLOWS.values():
            flows.update(type_flows)

    flows.update(
        [
            integration.domain
            for integration in integrations.values()
            if integration.config_flow
            and (type_filter is None or integration.integration_type == type_filter)
        ]
    )

    return flows


class ComponentProtocol(Protocol):
    """Define the format of an integration."""

    CONFIG_SCHEMA: vol.Schema
    DOMAIN: str

    async def async_setup_entry(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up a config entry."""

    async def async_unload_entry(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload a config entry."""

    async def async_migrate_entry(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Migrate an old config entry."""

    async def async_remove_entry(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Remove a config entry."""

    async def async_remove_config_entry_device(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_entry: dr.DeviceEntry,
    ) -> bool:
        """Remove a config entry device."""

    async def async_reset_platform(
        self, hass: HomeAssistant, integration_name: str
    ) -> None:
        """Release resources."""

    async def async_setup(self, hass: HomeAssistant, config: ConfigType) -> bool:
        """Set up integration."""

    def setup(self, hass: HomeAssistant, config: ConfigType) -> bool:
        """Set up integration."""


async def async_get_integration_descriptions(
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Return cached list of integrations."""
    base = generated.__path__[0]
    config_flow_path = pathlib.Path(base) / "integrations.json"

    flow = await hass.async_add_executor_job(config_flow_path.read_text)
    core_flows = cast(dict[str, Any], json_loads(flow))
    custom_integrations = await async_get_custom_components(hass)
    custom_flows: dict[str, Any] = {
        "integration": {},
        "helper": {},
    }

    for integration in custom_integrations.values():
        # Remove core integration with same domain as the custom integration
        if integration.integration_type in ("entity", "system"):
            continue

        for integration_type in ("integration", "helper"):
            if integration.domain not in core_flows[integration_type]:
                continue
            del core_flows[integration_type][integration.domain]
        if integration.domain in core_flows["translated_name"]:
            core_flows["translated_name"].remove(integration.domain)

        if integration.integration_type == "helper":
            integration_key: str = integration.integration_type
        else:
            integration_key = "integration"

        metadata = {
            "config_flow": integration.config_flow,
            "integration_type": integration.integration_type,
            "iot_class": integration.iot_class,
            "name": integration.name,
        }
        custom_flows[integration_key][integration.domain] = metadata

    return {"core": core_flows, "custom": custom_flows}


async def async_get_application_credentials(hass: HomeAssistant) -> list[str]:
    """Return cached list of application credentials."""
    integrations = await async_get_custom_components(hass)

    return [
        *APPLICATION_CREDENTIALS,
        *[
            integration.domain
            for integration in integrations.values()
            if "application_credentials" in integration.dependencies
        ],
    ]


def async_process_zeroconf_match_dict(entry: dict[str, Any]) -> dict[str, Any]:
    """Handle backwards compat with zeroconf matchers."""
    entry_without_type: dict[str, Any] = entry.copy()
    del entry_without_type["type"]
    # These properties keys used to be at the top level, we relocate
    # them for backwards compat
    for moved_prop in MOVED_ZEROCONF_PROPS:
        if value := entry_without_type.pop(moved_prop, None):
            _LOGGER.warning(
                (
                    'Matching the zeroconf property "%s" at top-level is deprecated and'
                    " should be moved into a properties dict; Check the developer"
                    " documentation"
                ),
                moved_prop,
            )
            if "properties" not in entry_without_type:
                prop_dict: dict[str, str] = {}
                entry_without_type["properties"] = prop_dict
            else:
                prop_dict = entry_without_type["properties"]
            prop_dict[moved_prop] = value.lower()
    return entry_without_type


async def async_get_zeroconf(
    hass: HomeAssistant,
) -> dict[str, list[dict[str, str | dict[str, str]]]]:
    """Return cached list of zeroconf types."""
    zeroconf: dict[
        str, list[dict[str, str | dict[str, str]]]
    ] = ZEROCONF.copy()  # type: ignore[assignment]

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.zeroconf:
            continue
        for entry in integration.zeroconf:
            data: dict[str, str | dict[str, str]] = {"domain": integration.domain}
            if isinstance(entry, dict):
                typ = entry["type"]
                data.update(async_process_zeroconf_match_dict(entry))
            else:
                typ = entry

            zeroconf.setdefault(typ, []).append(data)

    return zeroconf


async def async_get_bluetooth(hass: HomeAssistant) -> list[BluetoothMatcher]:
    """Return cached list of bluetooth types."""
    bluetooth = cast(list[BluetoothMatcher], BLUETOOTH.copy())

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.bluetooth:
            continue
        for entry in integration.bluetooth:
            bluetooth.append(
                cast(BluetoothMatcher, {"domain": integration.domain, **entry})
            )

    return bluetooth


async def async_get_dhcp(hass: HomeAssistant) -> list[DHCPMatcher]:
    """Return cached list of dhcp types."""
    dhcp = cast(list[DHCPMatcher], DHCP.copy())

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.dhcp:
            continue
        for entry in integration.dhcp:
            dhcp.append(cast(DHCPMatcher, {"domain": integration.domain, **entry}))

    return dhcp


async def async_get_usb(hass: HomeAssistant) -> list[USBMatcher]:
    """Return cached list of usb types."""
    usb = cast(list[USBMatcher], USB.copy())

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.usb:
            continue
        for entry in integration.usb:
            usb.append(
                cast(
                    USBMatcher,
                    {
                        "domain": integration.domain,
                        **{k: v for k, v in entry.items() if k != "known_devices"},
                    },
                )
            )

    return usb


def homekit_always_discover(iot_class: str | None) -> bool:
    """Return if we should always offer HomeKit control for a device."""
    #
    # Since we prefer local control, if the integration that is being
    # discovered is cloud AND the HomeKit device is UNPAIRED we still
    # want to discovery it.
    #
    # Additionally if the integration is polling, HKC offers a local
    # push experience for the user to control the device so we want
    # to offer that as well.
    #
    return not iot_class or (iot_class.startswith("cloud") or "polling" in iot_class)


async def async_get_homekit(
    hass: HomeAssistant,
) -> dict[str, HomeKitDiscoveredIntegration]:
    """Return cached list of homekit models."""
    homekit: dict[str, HomeKitDiscoveredIntegration] = {
        model: HomeKitDiscoveredIntegration(
            cast(str, details["domain"]), cast(bool, details["always_discover"])
        )
        for model, details in HOMEKIT.items()
    }

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if (
            not integration.homekit
            or "models" not in integration.homekit
            or not integration.homekit["models"]
        ):
            continue
        for model in integration.homekit["models"]:
            homekit[model] = HomeKitDiscoveredIntegration(
                integration.domain,
                homekit_always_discover(integration.iot_class),
            )

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
        for base in root_module.__path__:
            manifest_path = pathlib.Path(base) / domain / "manifest.json"

            if not manifest_path.is_file():
                continue

            try:
                manifest = cast(Manifest, json_loads(manifest_path.read_text()))
            except JSON_DECODE_EXCEPTIONS as err:
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
            if integration.version is None:
                _LOGGER.error(
                    (
                        "The custom integration '%s' does not have a version key in the"
                        " manifest file and was blocked from loading. See"
                        " https://developers.home-assistant.io"
                        "/blog/2021/01/29/custom-integration-changes#versions"
                        " for more details"
                    ),
                    integration.domain,
                )
                return None
            try:
                AwesomeVersion(
                    integration.version,
                    ensure_strategy=[
                        AwesomeVersionStrategy.CALVER,
                        AwesomeVersionStrategy.SEMVER,
                        AwesomeVersionStrategy.SIMPLEVER,
                        AwesomeVersionStrategy.BUILDVER,
                        AwesomeVersionStrategy.PEP440,
                    ],
                )
            except AwesomeVersionException:
                _LOGGER.error(
                    (
                        "The custom integration '%s' does not have a valid version key"
                        " (%s) in the manifest file and was blocked from loading. See"
                        " https://developers.home-assistant.io"
                        "/blog/2021/01/29/custom-integration-changes#versions"
                        " for more details"
                    ),
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
    def loggers(self) -> list[str] | None:
        """Return list of loggers used by the integration."""
        return self.manifest.get("loggers")

    @property
    def quality_scale(self) -> str | None:
        """Return Integration Quality Scale."""
        return self.manifest.get("quality_scale")

    @property
    def iot_class(self) -> str | None:
        """Return the integration IoT Class."""
        return self.manifest.get("iot_class")

    @property
    def integration_type(
        self,
    ) -> Literal["entity", "device", "hardware", "helper", "hub", "service", "system"]:
        """Return the integration type."""
        return self.manifest.get("integration_type", "hub")

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
    def bluetooth(self) -> list[dict[str, str | int]] | None:
        """Return Integration bluetooth entries."""
        return self.manifest.get("bluetooth")

    @property
    def dhcp(self) -> list[dict[str, str | bool]] | None:
        """Return Integration dhcp entries."""
        return self.manifest.get("dhcp")

    @property
    def usb(self) -> list[dict[str, str]] | None:
        """Return Integration usb entries."""
        return self.manifest.get("usb")

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
                (
                    "Unable to resolve dependencies for %s:  we are unable to resolve"
                    " (sub)dependency %s"
                ),
                self.domain,
                err.domain,
            )
            self._all_dependencies_resolved = False
        except CircularDependency as err:
            _LOGGER.error(
                (
                    "Unable to resolve dependencies for %s:  it contains a circular"
                    " dependency: %s -> %s"
                ),
                self.domain,
                err.from_domain,
                err.to_domain,
            )
            self._all_dependencies_resolved = False

        return self._all_dependencies_resolved

    def get_component(self) -> ComponentProtocol:
        """Return the component."""
        cache: dict[str, ComponentProtocol] = self.hass.data[DATA_COMPONENTS]
        if self.domain in cache:
            return cache[self.domain]

        try:
            cache[self.domain] = cast(
                ComponentProtocol, importlib.import_module(self.pkg_path)
            )
        except ImportError:
            raise
        except Exception as err:
            _LOGGER.exception(
                "Unexpected exception importing component %s", self.pkg_path
            )
            raise ImportError(f"Exception importing {self.pkg_path}") from err

        return cache[self.domain]

    def get_platform(self, platform_name: str) -> ModuleType:
        """Return a platform for an integration."""
        cache: dict[str, ModuleType] = self.hass.data[DATA_COMPONENTS]
        full_name = f"{self.domain}.{platform_name}"
        if full_name in cache:
            return cache[full_name]

        try:
            cache[full_name] = self._import_platform(platform_name)
        except ImportError:
            raise
        except Exception as err:
            _LOGGER.exception(
                "Unexpected exception importing platform %s.%s",
                self.pkg_path,
                platform_name,
            )
            raise ImportError(
                f"Exception importing {self.pkg_path}.{platform_name}"
            ) from err

        return cache[full_name]

    def _import_platform(self, platform_name: str) -> ModuleType:
        """Import the platform."""
        return importlib.import_module(f"{self.pkg_path}.{platform_name}")

    def __repr__(self) -> str:
        """Text representation of class."""
        return f"<Integration {self.domain}: {self.pkg_path}>"


def _resolve_integrations_from_root(
    hass: HomeAssistant, root_module: ModuleType, domains: list[str]
) -> dict[str, Integration]:
    """Resolve multiple integrations from root."""
    integrations: dict[str, Integration] = {}
    for domain in domains:
        try:
            integration = Integration.resolve_from_root(hass, root_module, domain)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error loading integration: %s", domain)
        else:
            if integration:
                integrations[domain] = integration
    return integrations


@callback
def async_get_loaded_integration(hass: HomeAssistant, domain: str) -> Integration:
    """Get an integration which is already loaded.

    Raises IntegrationNotLoaded if the integration is not loaded.
    """
    cache = hass.data[DATA_INTEGRATIONS]
    if TYPE_CHECKING:
        cache = cast(dict[str, Integration | asyncio.Future[None]], cache)
    int_or_fut = cache.get(domain, _UNDEF)
    # Integration is never subclassed, so we can check for type
    if type(int_or_fut) is Integration:  # noqa: E721
        return int_or_fut
    raise IntegrationNotLoaded(domain)


async def async_get_integration(hass: HomeAssistant, domain: str) -> Integration:
    """Get integration."""
    integrations_or_excs = await async_get_integrations(hass, [domain])
    int_or_exc = integrations_or_excs[domain]
    if isinstance(int_or_exc, Integration):
        return int_or_exc
    raise int_or_exc


async def async_get_integrations(
    hass: HomeAssistant, domains: Iterable[str]
) -> dict[str, Integration | Exception]:
    """Get integrations."""
    cache = hass.data[DATA_INTEGRATIONS]
    results: dict[str, Integration | Exception] = {}
    needed: dict[str, asyncio.Future[None]] = {}
    in_progress: dict[str, asyncio.Future[None]] = {}
    if TYPE_CHECKING:
        cache = cast(dict[str, Integration | asyncio.Future[None]], cache)
    for domain in domains:
        int_or_fut = cache.get(domain, _UNDEF)
        # Integration is never subclassed, so we can check for type
        if type(int_or_fut) is Integration:  # noqa: E721
            results[domain] = int_or_fut
        elif int_or_fut is not _UNDEF:
            in_progress[domain] = cast(asyncio.Future[None], int_or_fut)
        elif "." in domain:
            results[domain] = ValueError(f"Invalid domain {domain}")
        else:
            needed[domain] = cache[domain] = hass.loop.create_future()

    if in_progress:
        await asyncio.gather(*in_progress.values())
        for domain in in_progress:
            # When we have waited and it's _UNDEF, it doesn't exist
            # We don't cache that it doesn't exist, or else people can't fix it
            # and then restart, because their config will never be valid.
            if (int_or_fut := cache.get(domain, _UNDEF)) is _UNDEF:
                results[domain] = IntegrationNotFound(domain)
            else:
                results[domain] = cast(Integration, int_or_fut)

    if not needed:
        return results

    # First we look for custom components
    # Instead of using resolve_from_root we use the cache of custom
    # components to find the integration.
    custom = await async_get_custom_components(hass)
    for domain, future in needed.items():
        if integration := custom.get(domain):
            results[domain] = cache[domain] = integration
            future.set_result(None)

    for domain in results:
        if domain in needed:
            del needed[domain]

    # Now the rest use resolve_from_root
    if needed:
        from . import components  # pylint: disable=import-outside-toplevel

        integrations = await hass.async_add_executor_job(
            _resolve_integrations_from_root, hass, components, list(needed)
        )
        for domain, future in needed.items():
            int_or_exc = integrations.get(domain)
            if not int_or_exc:
                cache.pop(domain)
                results[domain] = IntegrationNotFound(domain)
            elif isinstance(int_or_exc, Exception):
                cache.pop(domain)
                exc = IntegrationNotFound(domain)
                exc.__cause__ = int_or_exc
                results[domain] = exc
            else:
                results[domain] = cache[domain] = int_or_exc
            future.set_result(None)

    return results


class LoaderError(Exception):
    """Loader base error."""


class IntegrationNotFound(LoaderError):
    """Raised when a component is not found."""

    def __init__(self, domain: str) -> None:
        """Initialize a component not found error."""
        super().__init__(f"Integration '{domain}' not found.")
        self.domain = domain


class IntegrationNotLoaded(LoaderError):
    """Raised when a component is not loaded."""

    def __init__(self, domain: str) -> None:
        """Initialize a component not found error."""
        super().__init__(f"Integration '{domain}' not loaded.")
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
) -> ComponentProtocol | None:
    """Try to load specified file.

    Looks in config dir first, then built-in components.
    Only returns it if also found to be valid.
    Async friendly.
    """
    with suppress(KeyError):
        return hass.data[DATA_COMPONENTS][  # type: ignore[no-any-return]
            comp_or_platform
        ]

    cache = hass.data[DATA_COMPONENTS]

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

            return cast(ComponentProtocol, module)

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
                    "Error loading %s. Make sure all dependencies are installed", path
                )

    return None


class ModuleWrapper:
    """Class to wrap a Python module and auto fill in hass argument."""

    def __init__(self, hass: HomeAssistant, module: ComponentProtocol) -> None:
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
        integration = self._hass.data[DATA_INTEGRATIONS].get(comp_name)

        if isinstance(integration, Integration):
            component: ComponentProtocol | None = integration.get_component()
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


def bind_hass(func: _CallableT) -> _CallableT:
    """Decorate function to indicate that first argument is hass.

    The use of this decorator is discouraged, and it should not be used
    for new functions.
    """
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


def _async_mount_config_dir(hass: HomeAssistant) -> None:
    """Mount config dir in order to load custom_component.

    Async friendly but not a coroutine.
    """
    if hass.config.config_dir not in sys.path:
        sys.path.insert(0, hass.config.config_dir)


def _lookup_path(hass: HomeAssistant) -> list[str]:
    """Return the lookup paths for legacy lookups."""
    if hass.config.safe_mode:
        return [PACKAGE_BUILTIN]
    return [PACKAGE_CUSTOM_COMPONENTS, PACKAGE_BUILTIN]


def is_component_module_loaded(hass: HomeAssistant, module: str) -> bool:
    """Test if a component module is loaded."""
    return module in hass.data[DATA_COMPONENTS]
