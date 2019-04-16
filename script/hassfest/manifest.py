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
    vol.Optional('after_dependencies'): [str],
    vol.Required('codeowners'): [str],
})


def validate_manifest(integration: Integration):
    """Validate manifest."""
    try:
        MANIFEST_SCHEMA(integration.manifest)
    except vol.Invalid as err:
        integration.add_error(
            'manifest',
            "Invalid manifest: {}".format(
                humanize_error(integration.manifest, err)))
        integration.manifest = None
        return

    if integration.manifest['domain'] != integration.path.name:
        integration.add_error('manifest', 'Domain does not match dir name')


def validate(integrations: Dict[str, Integration], config):
    """Handle all integrations manifests."""
    for integration in integrations.values():
        if integration.manifest:
            validate_manifest(integration)
