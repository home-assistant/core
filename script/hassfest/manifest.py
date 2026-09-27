"""Manifest validation."""

from enum import StrEnum, auto
import json
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import urlparse

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionException,
    AwesomeVersionStrategy,
)
import probatio
from probatio.humanize import humanize_error

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from script.util import sort_manifest as util_sort_manifest

from .model import Config, Integration, IntegrationType, ScaledQualityScaleTiers

DOCUMENTATION_URL_SCHEMA = "https"
DOCUMENTATION_URL_HOST = "www.home-assistant.io"
DOCUMENTATION_URL_PATH_PREFIX = "/integrations/"
DOCUMENTATION_URL_EXCEPTIONS = {"https://www.home-assistant.io/hassio"}

_CORE_DOCUMENTATION_BASE = "https://www.home-assistant.io/integrations"


class NonScaledQualityScaleTiers(StrEnum):
    """Supported manifest quality scales."""

    CUSTOM = auto()
    NO_SCORE = auto()
    INTERNAL = auto()
    LEGACY = auto()


SUPPORTED_QUALITY_SCALES = [
    value.name.lower()
    for enum in [ScaledQualityScaleTiers, NonScaledQualityScaleTiers]
    for value in enum
]
SUPPORTED_IOT_CLASSES = [
    "assumed_state",
    "calculated",
    "cloud_polling",
    "cloud_push",
    "local_polling",
    "local_push",
]

# List of integrations that are supposed to have no IoT class
NO_IOT_CLASS = [
    *{platform.value for platform in Platform},
    "api",
    "application_credentials",
    "auth",
    "automation",
    "battery",
    "blueprint",
    "brands",
    "color_extractor",
    "config",
    "configurator",
    "counter",
    "default_config",
    "device_automation",
    "device_tracker",
    "diagnostics",
    "door",
    "doorbell",
    "downloader",
    "ffmpeg",
    "file_upload",
    "frontend",
    "garage_door",
    "gate",
    "hardkernel",
    "hardware",
    "history",
    "homeassistant",
    "homeassistant_alerts",
    "homeassistant_connect_zbt2",
    "homeassistant_green",
    "homeassistant_hardware",
    "homeassistant_sky_connect",
    "homeassistant_yellow",
    "humidity",
    "illuminance",
    "image_upload",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "intent_script",
    "intent",
    "logbook",
    "logger",
    "lovelace",
    "map_tiles",
    "media_source",
    "moisture",
    "motion",
    "my",
    "occupancy",
    "onboarding",
    "panel_custom",
    "plant",
    "power",
    "profiler",
    "proxy",
    "python_script",
    "raspberry_pi",
    "recovery_mode",
    "repairs",
    "schedule",
    "script",
    "search",
    "system_health",
    "system_log",
    "tag",
    "temperature",
    "timer",
    "trace",
    "vibration",
    "web_rtc",
    "webhook",
    "websocket_api",
    "window",
    "zone",
]


def core_documentation_url(value: str) -> str:
    """Validate that a documentation url has the correct path and domain."""
    if value in DOCUMENTATION_URL_EXCEPTIONS:
        return value
    if not value.startswith(_CORE_DOCUMENTATION_BASE):
        raise probatio.Invalid(
            f"Documentation URL does not begin with {_CORE_DOCUMENTATION_BASE}"
        )

    return value


def custom_documentation_url(value: str) -> str:
    """Validate that a custom integration documentation url is correct."""
    parsed_url = urlparse(value)
    if parsed_url.scheme != DOCUMENTATION_URL_SCHEMA:
        raise probatio.Invalid("Documentation url is not prefixed with https")
    if value.startswith(_CORE_DOCUMENTATION_BASE):
        raise probatio.Invalid(
            "Documentation URL should point to the custom integration documentation"
        )

    return value


def verify_lowercase(value: str) -> str:
    """Verify a value is lowercase."""
    if value.lower() != value:
        raise probatio.Invalid("Value needs to be lowercase")

    return value


def verify_uppercase(value: str) -> str:
    """Verify a value is uppercase."""
    if value.upper() != value:
        raise probatio.Invalid("Value needs to be uppercase")

    return value


def verify_version(value: str) -> str:
    """Verify the version."""
    try:
        AwesomeVersion(
            value,
            ensure_strategy=[
                AwesomeVersionStrategy.CALVER,
                AwesomeVersionStrategy.SEMVER,
                AwesomeVersionStrategy.SIMPLEVER,
                AwesomeVersionStrategy.BUILDVER,
                AwesomeVersionStrategy.PEP440,
            ],
        )
    except AwesomeVersionException as err:
        raise probatio.Invalid(f"'{value}' is not a valid version.") from err
    return value


def verify_wildcard(value: str) -> str:
    """Verify the matcher contains a wildcard."""
    if "*" not in value:
        raise probatio.Invalid(f"'{value}' needs to contain a wildcard matcher")
    return value


INTEGRATION_MANIFEST_SCHEMA = probatio.Schema(
    {
        probatio.Required("domain"): str,
        probatio.Required("name"): str,
        probatio.Optional("integration_type", default="hub"): probatio.In(
            [t.value for t in IntegrationType if t != IntegrationType.VIRTUAL]
        ),
        probatio.Optional("config_flow"): bool,
        probatio.Optional("mqtt"): [str],
        probatio.Optional("zeroconf"): [
            probatio.Any(
                str,
                probatio.All(
                    cv.deprecated("macaddress"),
                    cv.deprecated("model"),
                    cv.deprecated("manufacturer"),
                    probatio.Schema(
                        {
                            probatio.Required("type"): str,
                            probatio.Optional("macaddress"): probatio.All(
                                str, verify_uppercase, verify_wildcard
                            ),
                            probatio.Optional("manufacturer"): probatio.All(
                                str, verify_lowercase
                            ),
                            probatio.Optional("model"): probatio.All(
                                str, verify_lowercase
                            ),
                            probatio.Optional("name"): probatio.All(
                                str, verify_lowercase
                            ),
                            probatio.Optional("properties"): probatio.Schema(
                                {str: verify_lowercase}
                            ),
                        }
                    ),
                ),
            )
        ],
        probatio.Optional("ssdp"): probatio.Schema(
            probatio.All(
                [
                    probatio.All(
                        probatio.Schema({}, extra=probatio.ALLOW_EXTRA),
                        probatio.Length(min=1),
                    )
                ]
            )
        ),
        probatio.Optional("bluetooth"): [
            probatio.Schema(
                {
                    probatio.Optional("connectable"): bool,
                    probatio.Optional("service_uuid"): probatio.All(
                        str, verify_lowercase
                    ),
                    probatio.Optional("service_data_uuid"): probatio.All(
                        str, verify_lowercase
                    ),
                    probatio.Optional("local_name"): probatio.All(str),
                    probatio.Optional("manufacturer_id"): int,
                    probatio.Optional("manufacturer_data_start"): [int],
                }
            )
        ],
        probatio.Optional("homekit"): probatio.Schema(
            {probatio.Optional("models"): [str]}
        ),
        probatio.Optional("dhcp"): [
            probatio.Schema(
                {
                    probatio.Optional("macaddress"): probatio.All(
                        str, verify_uppercase, verify_wildcard
                    ),
                    probatio.Optional("hostname"): probatio.All(str, verify_lowercase),
                    probatio.Optional("registered_devices"): cv.boolean,
                }
            )
        ],
        probatio.Optional("usb"): [
            probatio.Schema(
                {
                    probatio.Optional("vid"): probatio.All(str, verify_uppercase),
                    probatio.Optional("pid"): probatio.All(str, verify_uppercase),
                    probatio.Optional("serial_number"): probatio.All(
                        str, verify_lowercase
                    ),
                    probatio.Optional("manufacturer"): probatio.All(
                        str, verify_lowercase
                    ),
                    probatio.Optional("description"): probatio.All(
                        str, verify_lowercase
                    ),
                    probatio.Optional("known_devices"): [str],
                }
            )
        ],
        probatio.Required("documentation"): probatio.All(
            probatio.Url(), core_documentation_url
        ),
        probatio.Optional("quality_scale"): probatio.In(SUPPORTED_QUALITY_SCALES),
        probatio.Optional("requirements"): [str],
        probatio.Optional("dependencies"): [str],
        probatio.Optional("after_dependencies"): [str],
        probatio.Required("codeowners"): [str],
        probatio.Optional("loggers"): [str],
        probatio.Optional("disabled"): str,
        probatio.Optional("iot_class"): probatio.In(SUPPORTED_IOT_CLASSES),
        probatio.Optional("single_config_entry"): bool,
        probatio.Optional("preview_features"): probatio.Schema(
            {
                cv.slug: probatio.Schema(
                    {
                        probatio.Optional("feedback_url"): probatio.Url(),
                        probatio.Optional("learn_more_url"): probatio.Url(),
                        probatio.Optional("report_issue_url"): probatio.Url(),
                    }
                )
            }
        ),
    }
)

VIRTUAL_INTEGRATION_MANIFEST_SCHEMA = probatio.Schema(
    {
        probatio.Required("domain"): str,
        probatio.Required("name"): str,
        probatio.Required("integration_type"): IntegrationType.VIRTUAL.value,
        probatio.Exclusive("iot_standards", "virtual_integration"): [
            probatio.Any("homekit", "zigbee", "zwave")
        ],
        probatio.Exclusive("supported_by", "virtual_integration"): str,
    }
)


def manifest_schema(value: dict[str, Any]) -> probatio.Schema:
    """Validate integration manifest."""
    if value.get("integration_type") == IntegrationType.VIRTUAL:
        return VIRTUAL_INTEGRATION_MANIFEST_SCHEMA(value)
    return INTEGRATION_MANIFEST_SCHEMA(value)


CUSTOM_INTEGRATION_MANIFEST_SCHEMA = INTEGRATION_MANIFEST_SCHEMA.extend(
    {
        probatio.Required("documentation"): probatio.All(
            probatio.Url(), custom_documentation_url
        ),
        probatio.Optional("version"): probatio.All(str, verify_version),
        probatio.Optional("issue_tracker"): probatio.Url(),
        probatio.Optional("import_executor"): bool,
    }
)


def validate_version(integration: Integration) -> None:
    """Validate the version of the integration.

    Will be removed when the version key is no longer optional for custom integrations.
    """
    if not integration.manifest.get("version"):
        integration.add_error("manifest", "No 'version' key in the manifest file.")
        return


def validate_manifest(integration: Integration, core_components_dir: Path) -> None:
    """Validate manifest."""
    try:
        if integration.core:
            manifest_schema(integration.manifest)
        else:
            CUSTOM_INTEGRATION_MANIFEST_SCHEMA(integration.manifest)
    except probatio.Invalid as err:
        integration.add_error(
            "manifest", f"Invalid manifest: {humanize_error(integration.manifest, err)}"
        )

    if (domain := integration.manifest["domain"]) != integration.path.name:
        integration.add_error("manifest", "Domain does not match dir name")

    if not integration.core and (core_components_dir / domain).exists():
        integration.add_warning(
            "manifest", "Domain collides with built-in core integration"
        )

    if domain in NO_IOT_CLASS and "iot_class" in integration.manifest:
        integration.add_error("manifest", "Domain should not have an IoT Class")

    if (
        domain not in NO_IOT_CLASS
        and "iot_class" not in integration.manifest
        and integration.integration_type != IntegrationType.VIRTUAL
    ):
        integration.add_error("manifest", "Domain is missing an IoT Class")

    if (
        integration.integration_type == IntegrationType.VIRTUAL
        and (supported_by := integration.manifest.get("supported_by"))
        and not (core_components_dir / supported_by).exists()
    ):
        integration.add_error(
            "manifest",
            "Virtual integration points to non-existing supported_by integration",
        )

    if (
        (quality_scale := integration.manifest.get("quality_scale"))
        and quality_scale.upper() in ScaledQualityScaleTiers
        and ScaledQualityScaleTiers[quality_scale.upper()]
        >= ScaledQualityScaleTiers.SILVER
    ):
        if not integration.manifest.get("codeowners"):
            integration.add_error(
                "manifest",
                f"{quality_scale} integration does not have a code owner",
            )

    if not integration.core:
        validate_version(integration)


def sort_manifest(integration: Integration, config: Config) -> bool:
    """Sort manifest."""
    if integration.manifest_path is None:
        integration.add_error(
            "manifest",
            "Manifest path not set, unable to sort manifest keys",
        )
        return False

    if util_sort_manifest(integration.manifest):
        if config.action == "generate":
            integration.manifest_path.write_text(
                json.dumps(integration.manifest, indent=2) + "\n"
            )
            text = "have been sorted"
        else:
            text = "are not sorted correctly"
        integration.add_error(
            "manifest",
            f"Manifest keys {text}: domain, name, then alphabetical order",
        )
        return True
    return False


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle all integrations manifests."""
    core_components_dir = config.root / "homeassistant/components"
    manifests_resorted = []
    for integration in integrations.values():
        validate_manifest(integration, core_components_dir)
        if not integration.errors:
            if sort_manifest(integration, config):
                manifests_resorted.append(integration.manifest_path)
    if config.action == "generate" and manifests_resorted:
        subprocess.run(
            [
                "prek",
                "run",
                "--hook-stage",
                "manual",
                "prettier",
                "--files",
                *manifests_resorted,
            ],
            stdout=subprocess.DEVNULL,
            check=True,
        )
