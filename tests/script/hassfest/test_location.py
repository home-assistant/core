"""Tests for hassfest location generation."""

from pathlib import Path

from hassfest.model import Config
import pytest

from script.hassfest import location

from . import get_integration


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Return a hassfest config."""
    return Config(
        root=tmp_path,
        specific_integrations=None,
        action="validate",
        requirements=False,
    )


def test_generate(config: Config) -> None:
    """Test the integrations are grouped by country."""
    integration_1 = get_integration("test_1", config)
    integration_1.manifest["locations"] = ["NL", "BE"]
    integration_2 = get_integration("test_2", config)
    integration_2.manifest["locations"] = ["NL"]

    content = location.generate_and_validate(
        {"test_2": integration_2, "test_1": integration_1}, config
    )

    assert config.errors == []
    assert '"BE": [\n        "test_1",\n    ],' in content
    assert '"NL": [\n        "test_1",\n        "test_2",\n    ],' in content
