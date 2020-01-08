"""Manifest validation."""
from typing import Dict

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .model import Integration

SUPPORTED_QUALITY_SCALES = [
    "gold",
    "internal",
    "platinum",
    "silver",
]

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
        vol.Required("documentation"): str,
        vol.Optional("quality_scale"): vol.In(SUPPORTED_QUALITY_SCALES),
        vol.Required("requirements"): [str],
        vol.Required("dependencies"): [str],
        vol.Optional("after_dependencies"): [str],
        vol.Required("codeowners"): [str],
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
