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
    get_imported_integrations,
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


DEPENDENCIES = {
    "cast": [],
    "http": [],
    "lovelace": [],
    "plex": [],
    "twilio": ["http"],
    "twilio_call": ["twilio"],
    "twilio_sms": ["twilio"],
}
SOURCES = {
    # An integration platform, coupled without declaring the dependency
    "lovelace": "from homeassistant.components.cast.services import ATTR_URL_PATH",
    # Imports are not followed transitively, so this must not reach cast
    "plex": "from homeassistant.components import lovelace",
    # http is in the core files, so it is left out
    "twilio": "import homeassistant.components.http",
}


@pytest.fixture
def components_dir(tmp_path: Path) -> Generator[Path]:
    """Create integrations with a dependency on each other."""
    components_dir = tmp_path / "homeassistant" / "components"
    for integration, integration_dependencies in DEPENDENCIES.items():
        integration_dir = components_dir / integration
        integration_dir.mkdir(parents=True)
        (integration_dir / "manifest.json").write_text(
            json.dumps(
                {"domain": integration, "dependencies": integration_dependencies}
            )
        )
        (integration_dir / "__init__.py").write_text(SOURCES.get(integration, ""))
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


@pytest.mark.usefixtures("components_dir")
def test_get_imported_integrations() -> None:
    """Test that imported integrations are detected."""
    assert get_imported_integrations(DEPENDENCIES) == {
        "cast": set(),
        "http": set(),
        "lovelace": {"cast"},
        "plex": {"lovelace"},
        "twilio": {"http"},
        "twilio_call": set(),
        "twilio_sms": set(),
    }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "from homeassistant.components.cast import DOMAIN", {"cast"}, id="from"
        ),
        pytest.param(
            "from homeassistant.components.cast.services import ATTR_URL_PATH",
            {"cast"},
            id="from-submodule",
        ),
        pytest.param("import homeassistant.components.cast", {"cast"}, id="import"),
        pytest.param(
            "from homeassistant.components import cast, plex",
            {"cast", "plex"},
            id="from-package",
        ),
        pytest.param(
            "from homeassistant.components import (\n    cast,\n    plex,\n)",
            {"cast", "plex"},
            id="from-package-parenthesized",
        ),
        pytest.param(
            "from homeassistant.components.unknown import DOMAIN", set(), id="unknown"
        ),
        pytest.param(
            "from homeassistant.helpers import device_registry", set(), id="helper"
        ),
    ],
)
@pytest.mark.usefixtures("core_files")
def test_get_imported_integrations_patterns(
    tmp_path: Path, source: str, expected: set[str]
) -> None:
    """Test the import patterns that are picked up."""
    components_dir = tmp_path / "homeassistant" / "components"
    for integration in ("cast", "lovelace", "plex"):
        (components_dir / integration).mkdir(parents=True)
    (components_dir / "lovelace" / "__init__.py").write_text(source)

    with patch.object(gen_integration_paths, "COMPONENTS_DIR", components_dir):
        imported = get_imported_integrations(["cast", "lovelace", "plex"])

    assert imported["lovelace"] == expected


@pytest.mark.usefixtures("components_dir", "core_files")
def test_generate() -> None:
    """Test that dependencies and imports are added, except core integrations."""
    assert generate() == (
        "cast: [homeassistant/components/cast/**, tests/components/cast/**]\n"
        "http: [homeassistant/components/http/**, tests/components/http/**]\n"
        "lovelace: [homeassistant/components/lovelace/**, "
        "tests/components/lovelace/**, homeassistant/components/cast/**]\n"
        "plex: [homeassistant/components/plex/**, tests/components/plex/**, "
        "homeassistant/components/lovelace/**]\n"
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
