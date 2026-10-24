"""Tests for hassfest metadata validation and codemeta generation."""

from copy import replace
import json
from pathlib import Path

import pytest

from homeassistant.const import REQUIRED_PYTHON_VER, __version__
from script.hassfest.metadata import (
    CODEMETA_PATH,
    _format_author,
    _format_license,
    _parse_classifiers,
    generate,
    validate,
)
from script.hassfest.model import Config


def _create_pyproject_toml(
    tmp_path: Path,
    version: str = __version__,
    requires_python: str = f">={'.'.join(map(str, REQUIRED_PYTHON_VER))}",
) -> Path:
    """Create a minimal pyproject.toml in tmp_path."""
    pyproject = f"""[project]
name = "homeassistant"
version = "{version}"
license = "Apache-2.0"
description = "Open-source home automation platform running on Python 3."
readme = "README.rst"
authors = [
  {{ name = "The Home Assistant Authors", email = "hello@home-assistant.io" }},
]
keywords = ["home", "automation"]
classifiers = [
  "Development Status :: 5 - Production/Stable",
  "Intended Audience :: Developers",
  "Operating System :: OS Independent",
  "Programming Language :: Python :: 3.14",
  "Topic :: Home Automation",
]
requires-python = "{requires_python}"

[project.urls]
"Homepage" = "https://www.home-assistant.io/"
"Source Code" = "https://github.com/home-assistant/core"
"Bug Reports" = "https://github.com/home-assistant/core/issues"
"Docs: Dev" = "https://contributors.home-assistant.io/"
"Discord" = "https://www.home-assistant.io/join-chat/"
"""
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(pyproject, encoding="utf-8")
    return pyproject_path


@pytest.mark.parametrize(
    ("license_entry", "expected_url"),
    [
        ("Apache-2.0", "https://spdx.org/licenses/Apache-2.0"),
        ("MIT", "https://spdx.org/licenses/MIT"),
        ("https://custom.org/license", "https://custom.org/license"),
        ({"text": "Apache-2.0"}, "https://spdx.org/licenses/Apache-2.0"),
    ],
)
def test_format_license(license_entry: str | dict[str, str], expected_url: str) -> None:
    """Test formatting license strings and dicts."""
    assert _format_license(license_entry) == expected_url


@pytest.mark.parametrize(
    ("author_data", "expected_type", "expected_name", "expected_email"),
    [
        (
            {"name": "The Home Assistant Authors", "email": "hello@home-assistant.io"},
            "Organization",
            "The Home Assistant Authors",
            "hello@home-assistant.io",
        ),
        (
            {"name": "Home Assistant Team"},
            "Organization",
            "Home Assistant Team",
            None,
        ),
        (
            {"name": "Jane Doe", "email": "jane@example.com"},
            "Person",
            "Jane Doe",
            "jane@example.com",
        ),
    ],
)
def test_format_author(
    author_data: dict[str, str],
    expected_type: str,
    expected_name: str,
    expected_email: str | None,
) -> None:
    """Test formatting authors into Organization or Person."""
    result = _format_author(author_data)
    assert result["@type"] == expected_type
    assert result.get("name") == expected_name
    assert result.get("email") == expected_email


def test_parse_classifiers() -> None:
    """Test parsing classifiers into CodeMeta properties."""
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.14",
        "Topic :: Home Automation",
    ]
    result = _parse_classifiers(classifiers)
    assert result["programmingLanguage"] == ["Python"]
    assert result["operatingSystem"] == ["OS Independent"]
    assert result["audience"] == ["Developers"]
    assert result["applicationCategory"] == "Home Automation"
    assert result["developmentStatus"] == "Production/Stable"


def test_validate_metadata_success(config: Config, tmp_path: Path) -> None:
    """Test validation succeeds when codemeta.json is up to date."""
    _create_pyproject_toml(tmp_path)
    cfg = replace(config, root=tmp_path)
    generate({}, cfg)

    validate({}, cfg)
    assert not cfg.errors


def test_validate_metadata_missing_codemeta(config: Config, tmp_path: Path) -> None:
    """Test validation reports fixable error when codemeta.json is missing."""
    _create_pyproject_toml(tmp_path)
    cfg = replace(config, root=tmp_path)

    validate({}, cfg)
    assert len(cfg.errors) == 1
    assert cfg.errors[0].plugin == "metadata"
    assert cfg.errors[0].fixable is True
    assert "codemeta.json is not up to date" in cfg.errors[0].error


def test_validate_metadata_stale_codemeta(config: Config, tmp_path: Path) -> None:
    """Test validation reports fixable error when codemeta.json is stale."""
    _create_pyproject_toml(tmp_path)
    (tmp_path / CODEMETA_PATH).write_text("{}", encoding="utf-8")
    cfg = replace(config, root=tmp_path)

    validate({}, cfg)
    assert len(cfg.errors) == 1
    assert cfg.errors[0].plugin == "metadata"
    assert cfg.errors[0].fixable is True


def test_validate_metadata_version_mismatch(config: Config, tmp_path: Path) -> None:
    """Test validation reports error on version mismatch."""
    _create_pyproject_toml(tmp_path, version="1999.1.0")
    cfg = replace(config, root=tmp_path)

    validate({}, cfg)
    assert any("project.version" in err.error for err in cfg.errors)


def test_validate_metadata_python_mismatch(config: Config, tmp_path: Path) -> None:
    """Test validation reports error on requires-python mismatch."""
    _create_pyproject_toml(tmp_path, requires_python=">=3.10")
    cfg = replace(config, root=tmp_path)

    validate({}, cfg)
    assert any("project.requires-python" in err.error for err in cfg.errors)


def test_generate_codemeta(config: Config, tmp_path: Path) -> None:
    """Test generate creates codemeta.json with expected structure."""
    _create_pyproject_toml(tmp_path)
    cfg = replace(config, root=tmp_path)

    generate({}, cfg)
    codemeta_file = tmp_path / CODEMETA_PATH
    assert codemeta_file.is_file()

    content = json.loads(codemeta_file.read_text(encoding="utf-8"))
    assert content["@context"] == "https://doi.org/10.5063/schema/codemeta-2.0"
    assert content["@type"] == "SoftwareSourceCode"
    assert content["identifier"] == "homeassistant"
    assert content["name"] == "homeassistant"
    assert content["license"] == "https://spdx.org/licenses/Apache-2.0"
    assert content["url"] == "https://www.home-assistant.io/"
    assert content["codeRepository"] == "https://github.com/home-assistant/core"
    assert content["issueTracker"] == "https://github.com/home-assistant/core/issues"
    assert content["softwareHelp"] == "https://contributors.home-assistant.io/"
    assert content["relatedLink"] == ["https://www.home-assistant.io/join-chat/"]
    assert content["applicationCategory"] == "Home Automation"
    assert content["audience"] == ["Developers"]
    assert content["developmentStatus"] == "Production/Stable"
    assert content["programmingLanguage"] == ["Python"]
