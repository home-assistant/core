"""Manifest validation."""
from typing import Dict

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .model import Integration


MANIFEST_SCHEMA = vol.Schema({
    vol.Required('domain'): str,
    vol.Required('name'): str,
    vol.Required('documentation'): str,
    vol.Required('requirements'): [str],
    vol.Required('dependencies'): [str],
    vol.Required('codeowners'): [str],
})


def validate_manifest(integration: Integration):
    """Validate manifest."""
    try:
        MANIFEST_SCHEMA(integration.manifest)
    except vol.Invalid as err:
        integration.errors.append(
            "Invalid manifest: {}".format(
                humanize_error(integration.manifest, err)))
        return

    if integration.manifest['domain'] != integration.path.name:
        integration.errors.append('Domain does not match dir name')


def validate_all(integrations: Dict[str, Integration]):
    """Validate all integrations manifests."""
    for integration in integrations.values():
        if integration.manifest:
            validate_manifest(integration)
