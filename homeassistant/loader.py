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
import os
import pathlib
import sys
import time
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypedDict, cast

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionException,
    AwesomeVersionStrategy,
)
from propcache import cached_property
import voluptuous as vol

from . import generated
from .const import Platform
from .core import HomeAssistant, callback
from .generated.application_credentials import APPLICATION_CREDENTIALS
from .generated.bluetooth import BLUETOOTH
from .generated.config_flows import FLOWS
from .generated.dhcp import DHCP
from .generated.mqtt import MQTT
from .generated.ssdp import SSDP
from .generated.usb import USB
from .generated.zeroconf import HOMEKIT, ZEROCONF
from .helpers.json import json_bytes, json_fragment
from .helpers.typing import UNDEFINED
from .util.hass_dict import HassKey
from .util.json import JSON_DECODE_EXCEPTIONS, json_loads

if TYPE_CHECKING:
    # The relative imports below are guarded by TYPE_CHECKING
    # because they would cause a circular import otherwise.
    from .config_entries import ConfigEntry
    from .helpers import device_registry as dr
    from .helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

#
# Integration.get_component will check preload platforms and
# try to import the code to avoid a thundering heard of import
# executor jobs later in the startup process.
#
# default platforms are prepopulated in this list to ensure that
# by the time the component is loaded, we check if the platform is
# available.
#
# This list can be extended by calling async_register_preload_platform
#
BASE_PRELOAD_PLATFORMS = [
    "config",
    "config_flow",
    "diagnostics",
    "energy",
    "group",
    "logbook",
    "hardware",
    "intent",
    "media_source",
    "recorder",
    "repairs",
    "system_health",
    "trigger",
]


@dataclass
class BlockedIntegration:
    """Blocked custom integration details."""

    lowest_good_version: AwesomeVersion | None
    reason: str


BLOCKED_CUSTOM_INTEGRATIONS: dict[str, BlockedIntegration] = {
    # Added in 2024.3.0 because of https://github.com/home-assistant/core/issues/112464
    "start_time": BlockedIntegration(AwesomeVersion("1.1.7"), "breaks Home Assistant"),
    # Added in 2024.5.1 because of
    # https://community.home-assistant.io/t/psa-2024-5-upgrade-failure-and-dreame-vacuum-custom-integration/724612
    "dreame_vacuum": BlockedIntegration(
        AwesomeVersion("1.0.4"), "crashes Home Assistant"
    ),
    # Added in 2024.5.5 because of
    # https://github.com/sh00t2kill/dolphin-robot/issues/185
    "mydolphin_plus": BlockedIntegration(
        AwesomeVersion("1.0.13"), "crashes Home Assistant"
    ),
    # Added in 2024.7.2 because of
    # https://github.com/gcobb321/icloud3/issues/349
    # Note: Current version 3.0.5.2, the fixed version is a guesstimate,
    # as no solution is available at time of writing.
    "icloud3": BlockedIntegration(
        AwesomeVersion("3.0.5.3"), "prevents recorder from working"
    ),
    # Added in 2024.7.2 because of
    # https://github.com/custom-components/places/issues/289
    "places": BlockedIntegration(
        AwesomeVersion("2.7.1"), "prevents recorder from working"
    ),
    # Added in 2024.7.2 because of
    # https://github.com/enkama/hass-variables/issues/120
    "variable": BlockedIntegration(
        AwesomeVersion("3.4.4"), "prevents recorder from working"
    ),
}

DATA_COMPONENTS: HassKey[dict[str, ModuleType | ComponentProtocol]] = HassKey(
    "components"
)
DATA_INTEGRATIONS: HassKey[dict[str, Integration | asyncio.Future[None]]] = HassKey(
    "integrations"
)
DATA_MISSING_PLATFORMS: HassKey[dict[str, bool]] = HassKey("missing_platforms")
DATA_CUSTOM_COMPONENTS: HassKey[
    dict[str, Integration] | asyncio.Future[dict[str, Integration]]
] = HassKey("custom_components")
DATA_PRELOAD_PLATFORMS: HassKey[list[str]] = HassKey("preload_platforms")
PACKAGE_CUSTOM_COMPONENTS = "custom_components"
PACKAGE_BUILTIN = "homeassistant.components"
CUSTOM_WARNING = (
    "We found a custom integration %s which has not "
    "been tested by Home Assistant. This component might "
    "cause stability problems, be sure to disable it if you "
    "experience issues with Home Assistant"
)
IMPORT_EVENT_LOOP_WARNING = (
    "We found an integration %s which is configured to "
    "to import its code in the event loop. This component might "
    "cause stability problems, be sure to disable it if you "
    "experience issues with Home Assistant"
)

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
    """Matcher for the USB integration."""


@dataclass(slots=True)
class HomeKitDiscoveredIntegration:
    """HomeKit model."""

    domain: str
    always_discover: bool


class ZeroconfMatcher(TypedDict, total=False):
    """Matcher for zeroconf."""

    domain: str
    name: str
    properties: dict[str, str]


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
        "entity", "device", "hardware", "helper", "hub", "service", "system", "virtual"
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
    import_executor: bool
    single_config_entry: bool


def async_setup(hass: HomeAssistant) -> None:
    """Set up the necessary data structures."""
    _async_mount_config_dir(hass)
    hass.data[DATA_COMPONENTS] = {}
    hass.data[DATA_INTEGRATIONS] = {}
    hass.data[DATA_MISSING_PLATFORMS] = {}
    hass.data[DATA_PRELOAD_PLATFORMS] = BASE_PRELOAD_PLATFORMS.copy()


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
    if hass.config.recovery_mode or hass.config.safe_mode:
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
    comps_or_future = hass.data.get(DATA_CUSTOM_COMPONENTS)

    if comps_or_future is None:
        future = hass.data[DATA_CUSTOM_COMPONENTS] = hass.loop.create_future()

        comps = await _async_get_custom_components(hass)

        hass.data[DATA_CUSTOM_COMPONENTS] = comps
        future.set_result(comps)
        return comps

    if isinstance(comps_or_future, asyncio.Future):
        return await comps_or_future

    return comps_or_future


async def async_get_config_flows(
    hass: HomeAssistant,
    type_filter: Literal["device", "helper", "hub", "service"] | None = None,
) -> set[str]:
    """Return cached list of config flows."""
    integrations = await async_get_custom_components(hass)
    flows: set[str] = set()

    if type_filter is not None:
        flows.update(FLOWS[type_filter])
    else:
        for type_flows in FLOWS.values():
            flows.update(type_flows)

    flows.update(
        integration.domain
        for integration in integrations.values()
        if integration.config_flow
        and (type_filter is None or integration.integration_type == type_filter)
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
            "single_config_entry": integration.manifest.get(
                "single_config_entry", False
            ),
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


def async_process_zeroconf_match_dict(entry: dict[str, Any]) -> ZeroconfMatcher:
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
    return cast(ZeroconfMatcher, entry_without_type)


async def async_get_zeroconf(
    hass: HomeAssistant,
) -> dict[str, list[ZeroconfMatcher]]:
    """Return cached list of zeroconf types."""
    zeroconf: dict[str, list[ZeroconfMatcher]] = ZEROCONF.copy()  # type: ignore[assignment]

    integrations = await async_get_custom_components(hass)
    for integration in integrations.values():
        if not integration.zeroconf:
            continue
        for entry in integration.zeroconf:
            data: ZeroconfMatcher = {"domain": integration.domain}
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


@callback
def async_register_preload_platform(hass: HomeAssistant, platform_name: str) -> None:
    """Register a platform to be preloaded."""
    preload_platforms = hass.data[DATA_PRELOAD_PLATFORMS]
    if platform_name not in preload_platforms:
        preload_platforms.append(platform_name)


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

            file_path = manifest_path.parent
            # Avoid the listdir for virtual integrations
            # as they cannot have any platforms
            is_virtual = manifest.get("integration_type") == "virtual"
            integration = cls(
                hass,
                f"{root_module.__name__}.{domain}",
                file_path,
                manifest,
                None if is_virtual else set(os.listdir(file_path)),
            )

            if not integration.import_executor:
                _LOGGER.warning(IMPORT_EVENT_LOOP_WARNING, integration.domain)

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

            if blocked := BLOCKED_CUSTOM_INTEGRATIONS.get(integration.domain):
                if _version_blocked(integration.version, blocked):
                    _LOGGER.error(
                        (
                            "Version %s of custom integration '%s' %s and was blocked "
                            "from loading, please %s"
                        ),
                        integration.version,
                        integration.domain,
                        blocked.reason,
                        async_suggest_report_issue(None, integration=integration),
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
        top_level_files: set[str] | None = None,
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

        self._platforms_to_preload = hass.data[DATA_PRELOAD_PLATFORMS]
        self._component_future: asyncio.Future[ComponentProtocol] | None = None
        self._import_futures: dict[str, asyncio.Future[ModuleType]] = {}
        self._cache = hass.data[DATA_COMPONENTS]
        self._missing_platforms_cache = hass.data[DATA_MISSING_PLATFORMS]
        self._top_level_files = top_level_files or set()
        _LOGGER.info("Loaded %s from %s", self.domain, pkg_path)

    @cached_property
    def manifest_json_fragment(self) -> json_fragment:
        """Return manifest as a JSON fragment."""
        return json_fragment(json_bytes(self.manifest))

    @cached_property
    def name(self) -> str:
        """Return name."""
        return self.manifest["name"]

    @cached_property
    def disabled(self) -> str | None:
        """Return reason integration is disabled."""
        return self.manifest.get("disabled")

    @cached_property
    def domain(self) -> str:
        """Return domain."""
        return self.manifest["domain"]

    @cached_property
    def dependencies(self) -> list[str]:
        """Return dependencies."""
        return self.manifest.get("dependencies", [])

    @cached_property
    def after_dependencies(self) -> list[str]:
        """Return after_dependencies."""
        return self.manifest.get("after_dependencies", [])

    @cached_property
    def requirements(self) -> list[str]:
        """Return requirements."""
        return self.manifest.get("requirements", [])

    @cached_property
    def config_flow(self) -> bool:
        """Return config_flow."""
        return self.manifest.get("config_flow") or False

    @cached_property
    def documentation(self) -> str | None:
        """Return documentation."""
        return self.manifest.get("documentation")

    @cached_property
    def issue_tracker(self) -> str | None:
        """Return issue tracker link."""
        return self.manifest.get("issue_tracker")

    @cached_property
    def loggers(self) -> list[str] | None:
        """Return list of loggers used by the integration."""
        return self.manifest.get("loggers")

    @cached_property
    def quality_scale(self) -> str | None:
        """Return Integration Quality Scale."""
        return self.manifest.get("quality_scale")

    @cached_property
    def iot_class(self) -> str | None:
        """Return the integration IoT Class."""
        return self.manifest.get("iot_class")

    @cached_property
    def integration_type(
        self,
    ) -> Literal[
        "entity", "device", "hardware", "helper", "hub", "service", "system", "virtual"
    ]:
        """Return the integration type."""
        return self.manifest.get("integration_type", "hub")

    @cached_property
    def import_executor(self) -> bool:
        """Import integration in the executor."""
        # If the integration does not explicitly set import_executor, we default to
        # True.
        return self.manifest.get("import_executor", True)

    @cached_property
    def has_translations(self) -> bool:
        """Return if the integration has translations."""
        return "translations" in self._top_level_files

    @cached_property
    def has_services(self) -> bool:
        """Return if the integration has services."""
        return "services.yaml" in self._top_level_files

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

    @cached_property
    def single_config_entry(self) -> bool:
        """Return if the integration supports a single config entry only."""
        return self.manifest.get("single_config_entry", False)

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

        self._all_dependencies_resolved = False
        try:
            dependencies = await _async_component_dependencies(self.hass, self)
        except IntegrationNotFound as err:
            _LOGGER.error(
                (
                    "Unable to resolve dependencies for %s: unable to resolve"
                    " (sub)dependency %s"
                ),
                self.domain,
                err.domain,
            )
        except CircularDependency as err:
            _LOGGER.error(
                (
                    "Unable to resolve dependencies for %s: it contains a circular"
                    " dependency: %s -> %s"
                ),
                self.domain,
                err.from_domain,
                err.to_domain,
            )
        else:
            dependencies.discard(self.domain)
            self._all_dependencies = dependencies
            self._all_dependencies_resolved = True

        return self._all_dependencies_resolved

    async def async_get_component(self) -> ComponentProtocol:
        """Return the component.

        This method will load the component if it's not already loaded
        and will check if import_executor is set and load it in the executor,
        otherwise it will load it in the event loop.
        """
        domain = self.domain
        if domain in (cache := self._cache):
            return cache[domain]

        if self._component_future:
            return await self._component_future

        if debug := _LOGGER.isEnabledFor(logging.DEBUG):
            start = time.perf_counter()

        # Some integrations fail on import because they call functions incorrectly.
        # So we do it before validating config to catch these errors.
        load_executor = self.import_executor and (
            self.pkg_path not in sys.modules
            or (self.config_flow and f"{self.pkg_path}.config_flow" not in sys.modules)
        )
        if not load_executor:
            comp = self._get_component()
            if debug:
                _LOGGER.debug(
                    "Component %s import took %.3f seconds (loaded_executor=False)",
                    self.domain,
                    time.perf_counter() - start,
                )
            return comp

        self._component_future = self.hass.loop.create_future()
        try:
            try:
                comp = await self.hass.async_add_import_executor_job(
                    self._get_component, True
                )
            except ModuleNotFoundError:
                raise
            except ImportError as ex:
                load_executor = False
                _LOGGER.debug(
                    "Failed to import %s in executor", self.domain, exc_info=ex
                )
                # If importing in the executor deadlocks because there is a circular
                # dependency, we fall back to the event loop.
                comp = self._get_component()
            self._component_future.set_result(comp)
        except BaseException as ex:
            self._component_future.set_exception(ex)
            with suppress(BaseException):
                # Set the exception retrieved flag on the future since
                # it will never be retrieved unless there
                # are concurrent calls to async_get_component
                self._component_future.result()
            raise
        finally:
            self._component_future = None

        if debug:
            _LOGGER.debug(
                "Component %s import took %.3f seconds (loaded_executor=%s)",
                self.domain,
                time.perf_counter() - start,
                load_executor,
            )

        return comp

    def get_component(self) -> ComponentProtocol:
        """Return the component.

        This method must be thread-safe as it's called from the executor
        and the event loop.

        This method checks the cache and if the component is not loaded
        it will load it in the executor if import_executor is set, otherwise
        it will load it in the event loop.

        This is mostly a thin wrapper around importlib.import_module
        with a dict cache which is thread-safe since importlib has
        appropriate locks.
        """
        domain = self.domain
        if domain in (cache := self._cache):
            return cache[domain]
        return self._get_component()

    def _get_component(self, preload_platforms: bool = False) -> ComponentProtocol:
        """Return the component."""
        cache = self._cache
        domain = self.domain
        try:
            cache[domain] = cast(
                ComponentProtocol, importlib.import_module(self.pkg_path)
            )
        except ImportError:
            raise
        except RuntimeError as err:
            # _DeadlockError inherits from RuntimeError
            raise ImportError(f"RuntimeError importing {self.pkg_path}: {err}") from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected exception importing component %s", self.pkg_path
            )
            raise ImportError(f"Exception importing {self.pkg_path}") from err

        if preload_platforms:
            for platform_name in self.platforms_exists(self._platforms_to_preload):
                with suppress(ImportError):
                    self.get_platform(platform_name)

        return cache[domain]

    def _load_platforms(self, platform_names: Iterable[str]) -> dict[str, ModuleType]:
        """Load platforms for an integration."""
        return {
            platform_name: self._load_platform(platform_name)
            for platform_name in platform_names
        }

    async def async_get_platform(self, platform_name: str) -> ModuleType:
        """Return a platform for an integration."""
        # Fast path for a single platform when it is already cached.
        # This is the common case.
        if platform := self._cache.get(f"{self.domain}.{platform_name}"):
            return platform  # type: ignore[return-value]
        platforms = await self.async_get_platforms((platform_name,))
        return platforms[platform_name]

    async def async_get_platforms(
        self, platform_names: Iterable[Platform | str]
    ) -> dict[str, ModuleType]:
        """Return a platforms for an integration."""
        domain = self.domain
        platforms: dict[str, ModuleType] = {}

        load_executor_platforms: list[str] = []
        load_event_loop_platforms: list[str] = []
        in_progress_imports: dict[str, asyncio.Future[ModuleType]] = {}
        import_futures: list[tuple[str, asyncio.Future[ModuleType]]] = []

        for platform_name in platform_names:
            if platform := self._get_platform_cached_or_raise(platform_name):
                platforms[platform_name] = platform
                continue

            # Another call to async_get_platforms is already importing this platform
            if future := self._import_futures.get(platform_name):
                in_progress_imports[platform_name] = future
                continue

            full_name = f"{domain}.{platform_name}"
            if (
                self.import_executor
                and full_name not in self.hass.config.components
                and f"{self.pkg_path}.{platform_name}" not in sys.modules
            ):
                load_executor_platforms.append(platform_name)
            else:
                load_event_loop_platforms.append(platform_name)

            import_future = self.hass.loop.create_future()
            self._import_futures[platform_name] = import_future
            import_futures.append((platform_name, import_future))

        if load_executor_platforms or load_event_loop_platforms:
            if debug := _LOGGER.isEnabledFor(logging.DEBUG):
                start = time.perf_counter()

            try:
                if load_executor_platforms:
                    try:
                        platforms.update(
                            await self.hass.async_add_import_executor_job(
                                self._load_platforms, platform_names
                            )
                        )
                    except ModuleNotFoundError:
                        raise
                    except ImportError as ex:
                        _LOGGER.debug(
                            "Failed to import %s platforms %s in executor",
                            domain,
                            load_executor_platforms,
                            exc_info=ex,
                        )
                        # If importing in the executor deadlocks because there is a circular
                        # dependency, we fall back to the event loop.
                        load_event_loop_platforms.extend(load_executor_platforms)

                if load_event_loop_platforms:
                    platforms.update(self._load_platforms(platform_names))

                for platform_name, import_future in import_futures:
                    import_future.set_result(platforms[platform_name])

            except BaseException as ex:
                for _, import_future in import_futures:
                    import_future.set_exception(ex)
                    with suppress(BaseException):
                        # Set the exception retrieved flag on the future since
                        # it will never be retrieved unless there
                        # are concurrent calls to async_get_platforms
                        import_future.result()
                raise

            finally:
                for platform_name, _ in import_futures:
                    self._import_futures.pop(platform_name)

                if debug:
                    _LOGGER.debug(
                        "Importing platforms for %s executor=%s loop=%s took %.2fs",
                        domain,
                        load_executor_platforms,
                        load_event_loop_platforms,
                        time.perf_counter() - start,
                    )

        if in_progress_imports:
            for platform_name, future in in_progress_imports.items():
                platforms[platform_name] = await future

        return platforms

    def _get_platform_cached_or_raise(self, platform_name: str) -> ModuleType | None:
        """Return a platform for an integration from cache."""
        full_name = f"{self.domain}.{platform_name}"
        if full_name in self._cache:
            # the cache is either a ModuleType or a ComponentProtocol
            # but we only care about the ModuleType here
            return self._cache[full_name]  # type: ignore[return-value]
        if full_name in self._missing_platforms_cache:
            raise ModuleNotFoundError(
                f"Platform {full_name} not found",
                name=f"{self.pkg_path}.{platform_name}",
            )
        return None

    def platforms_are_loaded(self, platform_names: Iterable[str]) -> bool:
        """Check if a platforms are loaded for an integration."""
        return all(
            f"{self.domain}.{platform_name}" in self._cache
            for platform_name in platform_names
        )

    def get_platform_cached(self, platform_name: str) -> ModuleType | None:
        """Return a platform for an integration from cache."""
        return self._cache.get(f"{self.domain}.{platform_name}")  # type: ignore[return-value]

    def get_platform(self, platform_name: str) -> ModuleType:
        """Return a platform for an integration."""
        if platform := self._get_platform_cached_or_raise(platform_name):
            return platform
        return self._load_platform(platform_name)

    def platforms_exists(self, platform_names: Iterable[str]) -> list[str]:
        """Check if a platforms exists for an integration.

        This method is thread-safe and can be called from the executor
        or event loop without doing blocking I/O.
        """
        files = self._top_level_files
        domain = self.domain
        existing_platforms: list[str] = []
        missing_platforms = self._missing_platforms_cache
        for platform_name in platform_names:
            full_name = f"{domain}.{platform_name}"
            if full_name not in missing_platforms and (
                f"{platform_name}.py" in files or platform_name in files
            ):
                existing_platforms.append(platform_name)
                continue
            missing_platforms[full_name] = True

        return existing_platforms

    def _load_platform(self, platform_name: str) -> ModuleType:
        """Load a platform for an integration.

        This method must be thread-safe as it's called from the executor
        and the event loop.

        This is mostly a thin wrapper around importlib.import_module
        with a dict cache which is thread-safe since importlib has
        appropriate locks.
        """
        full_name = f"{self.domain}.{platform_name}"
        cache = self.hass.data[DATA_COMPONENTS]
        try:
            cache[full_name] = self._import_platform(platform_name)
        except ModuleNotFoundError:
            if self.domain in cache:
                # If the domain is loaded, cache that the platform
                # does not exist so we do not try to load it again
                self._missing_platforms_cache[full_name] = True
            raise
        except ImportError:
            raise
        except RuntimeError as err:
            # _DeadlockError inherits from RuntimeError
            raise ImportError(
                f"RuntimeError importing {self.pkg_path}.{platform_name}: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected exception importing platform %s.%s",
                self.pkg_path,
                platform_name,
            )
            raise ImportError(
                f"Exception importing {self.pkg_path}.{platform_name}"
            ) from err

        return cast(ModuleType, cache[full_name])

    def _import_platform(self, platform_name: str) -> ModuleType:
        """Import the platform.

        This method must be thread-safe as it's called from the executor
        and the event loop.
        """
        return importlib.import_module(f"{self.pkg_path}.{platform_name}")

    def __repr__(self) -> str:
        """Text representation of class."""
        return f"<Integration {self.domain}: {self.pkg_path}>"


def _version_blocked(
    integration_version: AwesomeVersion,
    blocked_integration: BlockedIntegration,
) -> bool:
    """Return True if the integration version is blocked."""
    if blocked_integration.lowest_good_version is None:
        return True

    if integration_version >= blocked_integration.lowest_good_version:
        return False

    return True


def _resolve_integrations_from_root(
    hass: HomeAssistant, root_module: ModuleType, domains: Iterable[str]
) -> dict[str, Integration]:
    """Resolve multiple integrations from root."""
    integrations: dict[str, Integration] = {}
    for domain in domains:
        try:
            integration = Integration.resolve_from_root(hass, root_module, domain)
        except Exception:
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
    int_or_fut = cache.get(domain, UNDEFINED)
    # Integration is never subclassed, so we can check for type
    if type(int_or_fut) is Integration:
        return int_or_fut
    raise IntegrationNotLoaded(domain)


async def async_get_integration(hass: HomeAssistant, domain: str) -> Integration:
    """Get integration."""
    cache = hass.data[DATA_INTEGRATIONS]
    if type(int_or_fut := cache.get(domain, UNDEFINED)) is Integration:
        return int_or_fut
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
    for domain in domains:
        int_or_fut = cache.get(domain, UNDEFINED)
        # Integration is never subclassed, so we can check for type
        if type(int_or_fut) is Integration:
            results[domain] = int_or_fut
        elif int_or_fut is not UNDEFINED:
            in_progress[domain] = cast(asyncio.Future[None], int_or_fut)
        elif "." in domain:
            results[domain] = ValueError(f"Invalid domain {domain}")
        else:
            needed[domain] = cache[domain] = hass.loop.create_future()

    if in_progress:
        await asyncio.wait(in_progress.values())
        for domain in in_progress:
            # When we have waited and it's UNDEFINED, it doesn't exist
            # We don't cache that it doesn't exist, or else people can't fix it
            # and then restart, because their config will never be valid.
            if (int_or_fut := cache.get(domain, UNDEFINED)) is UNDEFINED:
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
            _resolve_integrations_from_root, hass, components, needed
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

    def __init__(self, from_domain: str | set[str], to_domain: str) -> None:
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
    cache = hass.data[DATA_COMPONENTS]
    if module := cache.get(comp_or_platform):
        return cast(ComponentProtocol, module)

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

        # Local import to avoid circular dependencies
        from .helpers.frame import report  # pylint: disable=import-outside-toplevel

        report(
            (
                f"accesses hass.components.{comp_name}."
                " This is deprecated and will stop working in Home Assistant 2025.3, it"
                f" should be updated to import functions used from {comp_name} directly"
            ),
            error_if_core=False,
            log_custom_component_only=True,
        )

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

        # Local import to avoid circular dependencies
        from .helpers.frame import report  # pylint: disable=import-outside-toplevel

        report(
            (
                f"accesses hass.helpers.{helper_name}."
                " This is deprecated and will stop working in Home Assistant 2025.5, it"
                f" should be updated to import functions used from {helper_name} directly"
            ),
            error_if_core=False,
            log_custom_component_only=True,
        )

        wrapped = ModuleWrapper(self._hass, helper)
        setattr(self, helper_name, wrapped)
        return wrapped


def bind_hass[_CallableT: Callable[..., Any]](func: _CallableT) -> _CallableT:
    """Decorate function to indicate that first argument is hass.

    The use of this decorator is discouraged, and it should not be used
    for new functions.
    """
    setattr(func, "__bind_hass", True)
    return func


async def _async_component_dependencies(
    hass: HomeAssistant,
    integration: Integration,
) -> set[str]:
    """Get component dependencies."""
    loading: set[str] = set()
    loaded: set[str] = set()

    async def component_dependencies_impl(integration: Integration) -> None:
        """Recursively get component dependencies."""
        domain = integration.domain
        if not (dependencies := integration.dependencies):
            loaded.add(domain)
            return

        loading.add(domain)
        dep_integrations = await async_get_integrations(hass, dependencies)
        for dependency_domain, dep_integration in dep_integrations.items():
            if isinstance(dep_integration, Exception):
                raise dep_integration

            # If we are already loading it, we have a circular dependency.
            # We have to check it here to make sure that every integration that
            # depends on us, does not appear in our own after_dependencies.
            if conflict := loading.intersection(dep_integration.after_dependencies):
                raise CircularDependency(conflict, dependency_domain)

            # If we have already loaded it, no point doing it again.
            if dependency_domain in loaded:
                continue

            # If we are already loading it, we have a circular dependency.
            if dependency_domain in loading:
                raise CircularDependency(dependency_domain, domain)

            await component_dependencies_impl(dep_integration)
        loading.remove(domain)
        loaded.add(domain)

    await component_dependencies_impl(integration)

    return loaded


def _async_mount_config_dir(hass: HomeAssistant) -> None:
    """Mount config dir in order to load custom_component.

    Async friendly but not a coroutine.
    """

    sys.path.insert(0, hass.config.config_dir)
    with suppress(ImportError):
        import custom_components  # pylint: disable=import-outside-toplevel  # noqa: F401
    sys.path.remove(hass.config.config_dir)
    sys.path_importer_cache.pop(hass.config.config_dir, None)


def _lookup_path(hass: HomeAssistant) -> list[str]:
    """Return the lookup paths for legacy lookups."""
    if hass.config.recovery_mode or hass.config.safe_mode:
        return [PACKAGE_BUILTIN]
    return [PACKAGE_CUSTOM_COMPONENTS, PACKAGE_BUILTIN]


def is_component_module_loaded(hass: HomeAssistant, module: str) -> bool:
    """Test if a component module is loaded."""
    return module in hass.data[DATA_COMPONENTS]


@callback
def async_get_issue_tracker(
    hass: HomeAssistant | None,
    *,
    integration: Integration | None = None,
    integration_domain: str | None = None,
    module: str | None = None,
) -> str | None:
    """Return a URL for an integration's issue tracker."""
    issue_tracker = (
        "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
    )
    if not integration and not integration_domain and not module:
        # If we know nothing about the entity, suggest opening an issue on HA core
        return issue_tracker

    if (
        not integration
        and (hass and integration_domain)
        and (comps_or_future := hass.data.get(DATA_CUSTOM_COMPONENTS))
        and not isinstance(comps_or_future, asyncio.Future)
    ):
        integration = comps_or_future.get(integration_domain)

    if not integration and (hass and integration_domain):
        with suppress(IntegrationNotLoaded):
            integration = async_get_loaded_integration(hass, integration_domain)

    if integration and not integration.is_built_in:
        return integration.issue_tracker

    if module and "custom_components" in module:
        return None

    if integration:
        integration_domain = integration.domain

    if integration_domain:
        issue_tracker += f"+label%3A%22integration%3A+{integration_domain}%22"
    return issue_tracker


@callback
def async_suggest_report_issue(
    hass: HomeAssistant | None,
    *,
    integration: Integration | None = None,
    integration_domain: str | None = None,
    module: str | None = None,
) -> str:
    """Generate a blurb asking the user to file a bug report."""
    issue_tracker = async_get_issue_tracker(
        hass,
        integration=integration,
        integration_domain=integration_domain,
        module=module,
    )

    if not issue_tracker:
        if integration:
            integration_domain = integration.domain
        if not integration_domain:
            return "report it to the custom integration author"
        return (
            f"report it to the author of the '{integration_domain}' "
            "custom integration"
        )

    return f"create a bug report at {issue_tracker}"
