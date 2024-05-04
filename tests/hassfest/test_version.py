"""Tests for hassfest version."""

import pytest
import voluptuous as vol

from script.hassfest.manifest import (
    CUSTOM_INTEGRATION_MANIFEST_SCHEMA,
    validate_version,
)
from script.hassfest.model import Integration


@pytest.fixture
def integration():
    """Fixture for hassfest integration model."""
    integration = Integration("")
    integration._manifest = {
        "domain": "test",
        "documentation": "https://example.com",
        "name": "test",
        "codeowners": ["@awesome"],
    }
    return integration


def test_validate_version_no_key(integration: Integration) -> None:
    """Test validate version with no key."""
    validate_version(integration)
    assert "No 'version' key in the manifest file." in [
        x.error for x in integration.errors
    ]


def test_validate_custom_integration_manifest(integration: Integration) -> None:
    """Test validate custom integration manifest."""

    with pytest.raises(vol.Invalid):
        integration.manifest["version"] = "lorem_ipsum"
        CUSTOM_INTEGRATION_MANIFEST_SCHEMA(integration.manifest)

    with pytest.raises(vol.Invalid):
        integration.manifest["version"] = None
        CUSTOM_INTEGRATION_MANIFEST_SCHEMA(integration.manifest)

    integration.manifest["version"] = "1"
    schema = CUSTOM_INTEGRATION_MANIFEST_SCHEMA(integration.manifest)
    assert schema["version"] == "1"
