"""Helpers to gather requirements from manifests."""
from .manifest_helper import iter_manifests


def gather_requirements_from_manifests(process_requirements, errors, reqs):
    """Gather all of the requirements from manifests."""
    for manifest in iter_manifests():
        assert manifest['domain']

        if manifest.get('requirements') is None:
            errors.append(
                'The manifest for component {} is invalid. Please run'
                'script/manifest/validate.py'.format(manifest['domain'])
            )
            continue

        process_requirements(
            errors,
            manifest['requirements'],
            'homeassistant.components.{}'.format(manifest['domain']),
            reqs
        )
