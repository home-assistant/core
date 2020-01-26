"""Manifest validation."""
from typing import Dict

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .model import Integration

DOCUMENTATION_URL_PREFIX = "https://www.home-assistant.io/integrations/"
DOCUMENTATION_URL_EXCEPTIONS = ["https://www.home-assistant.io/hassio"]

SUPPORTED_QUALITY_SCALES = [
    "gold",
    "internal",
    "platinum",
    "silver",
]


def documentation_url(value: str) -> str:
    """Validate that a documentation url starts with the correct prefix."""
    if (
        not value.startswith(DOCUMENTATION_URL_PREFIX)
        and value not in DOCUMENTATION_URL_EXCEPTIONS
    ):
        raise vol.Invalid(
            "Documentation url didn't begin with %s".format(DOCUMENTATION_URL_PREFIX)
        )
    return value


MANIFEST_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): str,
        vol.Required("name"): str,
        vol.Optional("config_flow"): bool,
        vol.Optional("zeroconf"): [str],
        vol.Optional("ssdp"): vol.Schema(
            vol.All([vol.All(vol.Schema({}, extra=vol.ALLOW_EXTRA), vol.Length(min=1))])
        ),
        vol.Optional("homekit"): vol.Schema({vol.Optional("models"): [str]}),
        vol.Required("documentation"): vol.All(
            vol.Url(), documentation_url
        ),  # pylint: disable=no-value-for-parameter
        vol.Optional("quality_scale"): vol.In(SUPPORTED_QUALITY_SCALES),
        vol.Required("requirements"): [str],
        vol.Required("dependencies"): [str],
        vol.Optional("after_dependencies"): [str],
        vol.Required("codeowners"): [str],
        vol.Optional("logo"): vol.Url(),  # pylint: disable=no-value-for-parameter
        vol.Optional("icon"): vol.Url(),  # pylint: disable=no-value-for-parameter
    }
)


def validate_manifest(integration: Integration):
    """Validate manifest."""
    try:
        MANIFEST_SCHEMA(integration.manifest)
    except vol.Invalid as err:
        integration.add_error(
            "manifest",
            "Invalid manifest: {}".format(humanize_error(integration.manifest, err)),
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
