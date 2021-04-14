"""Manifest validation."""
from __future__ import annotations

from urllib.parse import urlparse

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.loader import validate_custom_integration_version

from .model import Integration

DOCUMENTATION_URL_SCHEMA = "https"
DOCUMENTATION_URL_HOST = "www.home-assistant.io"
DOCUMENTATION_URL_PATH_PREFIX = "/integrations/"
DOCUMENTATION_URL_EXCEPTIONS = {"https://www.home-assistant.io/hassio"}

SUPPORTED_QUALITY_SCALES = ["gold", "internal", "platinum", "silver"]


def documentation_url(value: str) -> str:
    """Validate that a documentation url has the correct path and domain."""
    if value in DOCUMENTATION_URL_EXCEPTIONS:
        return value

    parsed_url = urlparse(value)
    if parsed_url.scheme != DOCUMENTATION_URL_SCHEMA:
        raise vol.Invalid("Documentation url is not prefixed with https")
    if parsed_url.netloc == DOCUMENTATION_URL_HOST and not parsed_url.path.startswith(
        DOCUMENTATION_URL_PATH_PREFIX
    ):
        raise vol.Invalid(
            "Documentation url does not begin with www.home-assistant.io/integrations"
        )

    return value


def verify_lowercase(value: str):
    """Verify a value is lowercase."""
    if value.lower() != value:
        raise vol.Invalid("Value needs to be lowercase")

    return value


def verify_uppercase(value: str):
    """Verify a value is uppercase."""
    if value.upper() != value:
        raise vol.Invalid("Value needs to be uppercase")

    return value


def verify_version(value: str):
    """Verify the version."""
    if not validate_custom_integration_version(value):
        raise vol.Invalid(
            f"'{value}' is not a valid version. This will cause a future version of Home Assistant to block this integration.",
        )
    return value


MANIFEST_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): str,
        vol.Required("name"): str,
        vol.Optional("config_flow"): bool,
        vol.Optional("mqtt"): [str],
        vol.Optional("zeroconf"): [
            vol.Any(
                str,
                vol.Schema(
                    {
                        vol.Required("type"): str,
                        vol.Optional("macaddress"): vol.All(str, verify_uppercase),
                        vol.Optional("name"): vol.All(str, verify_lowercase),
                    }
                ),
            )
        ],
        vol.Optional("ssdp"): vol.Schema(
            vol.All([vol.All(vol.Schema({}, extra=vol.ALLOW_EXTRA), vol.Length(min=1))])
        ),
        vol.Optional("homekit"): vol.Schema({vol.Optional("models"): [str]}),
        vol.Optional("dhcp"): [
            vol.Schema(
                {
                    vol.Optional("macaddress"): vol.All(str, verify_uppercase),
                    vol.Optional("hostname"): vol.All(str, verify_lowercase),
                }
            )
        ],
        vol.Required("documentation"): vol.All(
            vol.Url(), documentation_url  # pylint: disable=no-value-for-parameter
        ),
        vol.Optional(
            "issue_tracker"
        ): vol.Url(),  # pylint: disable=no-value-for-parameter
        vol.Optional("quality_scale"): vol.In(SUPPORTED_QUALITY_SCALES),
        vol.Optional("requirements"): [str],
        vol.Optional("dependencies"): [str],
        vol.Optional("after_dependencies"): [str],
        vol.Required("codeowners"): [str],
        vol.Optional("disabled"): str,
    }
)

CUSTOM_INTEGRATION_MANIFEST_SCHEMA = MANIFEST_SCHEMA.extend(
    {
        vol.Optional("version"): vol.All(str, verify_version),
    }
)


def validate_version(integration: Integration):
    """
    Validate the version of the integration.

    Will be removed when the version key is no longer optional for custom integrations.
    """
    if not integration.manifest.get("version"):
        integration.add_error(
            "manifest",
            "No 'version' key in the manifest file. This will cause a future version of Home Assistant to block this integration.",
        )
        return


def validate_manifest(integration: Integration):
    """Validate manifest."""
    try:
        if integration.core:
            MANIFEST_SCHEMA(integration.manifest)
        else:
            CUSTOM_INTEGRATION_MANIFEST_SCHEMA(integration.manifest)
    except vol.Invalid as err:
        integration.add_error(
            "manifest", f"Invalid manifest: {humanize_error(integration.manifest, err)}"
        )

    if integration.manifest["domain"] != integration.path.name:
        integration.add_error("manifest", "Domain does not match dir name")

    if not integration.core:
        validate_version(integration)


def validate(integrations: dict[str, Integration], config):
    """Handle all integrations manifests."""
    for integration in integrations.values():
        if integration.manifest:
            validate_manifest(integration)
