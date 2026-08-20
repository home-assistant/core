"""Tests for hassfest device_classes generation."""

import json
from pathlib import Path

import pytest

from script.hassfest.device_classes import (
    DEVICE_CLASS_ENUMS,
    PATH,
    find_undeclared_domains,
)
from script.hassfest.model import Config, Integration


@pytest.fixture
def entity_integrations(config: Config) -> dict[str, Integration]:
    """Return the entity integrations of the repository."""
    integrations = Integration.load_dir(config.core_integrations_path, config)
    return {
        domain: integration
        for domain, integration in integrations.items()
        if integration.manifest.get("integration_type") == "entity"
    }


def test_every_domain_is_declared(entity_integrations: dict[str, Integration]) -> None:
    """Test no domain defining a device class enum is missing from the generator."""
    assert find_undeclared_domains(entity_integrations) == set()


def test_undeclared_domain_is_reported(
    entity_integrations: dict[str, Integration],
) -> None:
    """Test a domain missing from the generator is reported."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delitem(DEVICE_CLASS_ENUMS, "infrared")

        assert find_undeclared_domains(entity_integrations) == {"infrared"}


def test_generated_file_matches_the_declared_enums() -> None:
    """Test the generated file is in sync with the declared enums."""
    device_classes = json.loads(Path(PATH).read_text(encoding="utf-8"))

    assert device_classes["device_classes"] == {
        domain: sorted(device_class.value for device_class in enum)
        for domain, enum in sorted(DEVICE_CLASS_ENUMS.items())
    }
