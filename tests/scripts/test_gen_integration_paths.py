"""Test the gen_integration_paths script."""

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from script import gen_integration_paths
from script.gen_integration_paths import (
    generate,
    get_core_integrations,
    get_transitive_dependencies,
    main,
)

CORE_FILES = """
base_platforms: &base_platforms
  - homeassistant/components/sensor/**

components: &components
  # http is used by a lot of integrations
  - homeassistant/components/http/**
"""


@pytest.fixture
def components_dir(tmp_path: Path) -> Generator[Path]:
    """Create integrations with a dependency on each other."""
    dependencies = {
        "http": [],
        "twilio": ["http"],
        "twilio_call": ["twilio"],
        "twilio_sms": ["twilio"],
    }
    components_dir = tmp_path / "homeassistant" / "components"
    for integration, integration_dependencies in dependencies.items():
        manifest_path = components_dir / integration / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            json.dumps(
                {"domain": integration, "dependencies": integration_dependencies}
            )
        )
    with patch.object(gen_integration_paths, "COMPONENTS_DIR", components_dir):
        yield components_dir


@pytest.fixture
def core_files(tmp_path: Path) -> Generator[Path]:
    """Create a core files config."""
    core_files = tmp_path / ".core_files.yaml"
    core_files.write_text(CORE_FILES)
    with patch.object(gen_integration_paths, "CORE_FILES", core_files):
        yield core_files


@pytest.mark.usefixtures("core_files")
def test_get_core_integrations() -> None:
    """Test that both base platforms and components are picked up."""
    assert get_core_integrations() == {"http", "sensor"}


@pytest.mark.parametrize(
    ("dependencies", "expected"),
    [
        pytest.param(
            {"a": ["b"], "b": [], "c": []},
            {"a": {"b"}, "b": set(), "c": set()},
            id="direct",
        ),
        pytest.param(
            {"a": ["b"], "b": ["c"], "c": []},
            {"a": {"b", "c"}, "b": {"c"}, "c": set()},
            id="transitive",
        ),
        pytest.param(
            {"a": ["b"], "b": ["a"]},
            {"a": {"b"}, "b": {"a"}},
            id="cycle",
        ),
        pytest.param(
            {"a": ["a"]},
            {"a": set()},
            id="self",
        ),
        pytest.param(
            {"a": ["missing"]},
            {"a": set()},
            id="unknown-dependency",
        ),
    ],
)
def test_get_transitive_dependencies(
    dependencies: dict[str, list[str]], expected: dict[str, set[str]]
) -> None:
    """Test that dependencies are resolved recursively."""
    assert get_transitive_dependencies(dependencies) == expected


@pytest.mark.usefixtures("components_dir", "core_files")
def test_generate() -> None:
    """Test that dependencies are added, except the ones triggering a full run."""
    assert generate() == (
        "http: [homeassistant/components/http/**, tests/components/http/**]\n"
        "twilio: [homeassistant/components/twilio/**, tests/components/twilio/**]\n"
        "twilio_call: [homeassistant/components/twilio_call/**, "
        "tests/components/twilio_call/**, homeassistant/components/twilio/**]\n"
        "twilio_sms: [homeassistant/components/twilio_sms/**, "
        "tests/components/twilio_sms/**, homeassistant/components/twilio/**]\n"
    )


@pytest.mark.usefixtures("components_dir", "core_files")
def test_main(tmp_path: Path) -> None:
    """Test that the config is written to the output file."""
    output_file = tmp_path / ".integration_paths.yaml"
    with patch.object(gen_integration_paths, "OUTPUT_FILE", output_file):
        main()

    assert output_file.read_text() == generate()
