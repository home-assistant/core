"""Manifest validation."""
from typing import Dict
from urllib.parse import urlparse

import voluptuous as vol
from voluptuous.humanize import humanize_error

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


MANIFEST_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): str,
        vol.Required("name"): str,
        vol.Optional("config_flow"): bool,
        vol.Optional("zeroconf"): [
            vol.Any(
                str,
                vol.Schema(
                    {
                        vol.Required("type"): str,
                        vol.Optional("macaddress"): str,
                        vol.Optional("name"): str,
                    }
                ),
            )
        ],
        vol.Optional("ssdp"): vol.Schema(
            vol.All([vol.All(vol.Schema({}, extra=vol.ALLOW_EXTRA), vol.Length(min=1))])
        ),
        vol.Optional("homekit"): vol.Schema({vol.Optional("models"): [str]}),
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


def validate_manifest(integration: Integration):
    """Validate manifest."""
    try:
        MANIFEST_SCHEMA(integration.manifest)
    except vol.Invalid as err:
        integration.add_error(
            "manifest", f"Invalid manifest: {humanize_error(integration.manifest, err)}"
        )
        integration.manifest = None
        return

    if integration.manifest["domain"] != integration.path.name:
        integration.add_error("manifest", "Domain does not match dir name")


def validate(integrations: Dict[str, Integration], config):
    """Handle all integrations manifests."""
    for integration in integrations.values():
        if integration.manifest:
            validate_manifest(integration)
