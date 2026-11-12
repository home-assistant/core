"""Tests for the scaffold script."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from script.scaffold.gather_info import gather_info, gather_new_integration
from script.scaffold.generate import generate
from script.scaffold.model import Info

BASE_ANSWERS = ["Test", "developer", "", "local_polling"]


def test_new_integration_asks_for_categories() -> None:
    """Test a new integration gets categories that hassfest accepts."""
    answers = [
        *BASE_ANSWERS,
        "service",
        "yes",
        "no",
        "no",
        "",
        "not_a_category",
        "energy, energy.ev_charging",
        "energy, energy",
        "diy_makers, energy, sensors, weather_alerts",
        "energy.ev_charging, sensors",
    ]

    with patch("builtins.input", side_effect=answers) as mock_input:
        info = gather_new_integration(True)

    assert info["categories"] == ["energy.ev_charging", "sensors"]
    assert mock_input.call_count == len(answers)


@pytest.mark.parametrize("integration_type", ["entity", "system", "virtual"])
def test_new_integration_without_categories(integration_type: str) -> None:
    """Test integration types that need no categories are not asked for them."""
    with patch(
        "builtins.input",
        side_effect=[*BASE_ANSWERS, integration_type, "yes", "no", "no", "energy"],
    ):
        info = gather_new_integration(True)

    assert "categories" not in info


@pytest.mark.parametrize(
    ("determine_auth", "auth_answers"),
    [(True, ["yes", "no", "no"]), (False, [])],
)
def test_new_integration_requires_integration_type(
    determine_auth: bool, auth_answers: list[str]
) -> None:
    """Test every new integration gets the type hassfest needs for a config flow."""
    answers = [*BASE_ANSWERS, "", "omit", "service", *auth_answers, "sensors"]

    with patch("builtins.input", side_effect=answers) as mock_input:
        info = gather_new_integration(determine_auth)

    assert info["integration_type"] == "service"
    assert mock_input.call_count == len(answers)


def test_develop_integration_has_integration_type(tmp_path: Path) -> None:
    """Test developer mode sets the type hassfest needs for a config flow."""
    arguments = SimpleNamespace(integration=None, develop=True)

    with patch("script.scaffold.gather_info.COMPONENT_DIR", tmp_path):
        info = gather_info(arguments)

    assert info.integration_type == "hub"


def test_generate_integration_writes_categories(tmp_path: Path) -> None:
    """Test the generated manifest contains the gathered categories."""
    components = tmp_path / "components"
    tests = tmp_path / "tests"
    components.mkdir()
    tests.mkdir()
    info = Info(
        domain="test",
        name="Test",
        is_new=True,
        codeowner="@developer",
        iot_class="local_polling",
        categories=["energy.ev_charging", "sensors"],
    )

    with (
        patch("script.scaffold.model.COMPONENT_DIR", components),
        patch("script.scaffold.model.TESTS_DIR", tests),
    ):
        generate("integration", info)

    manifest = json.loads((components / "test" / "manifest.json").read_text())
    assert manifest["categories"] == ["energy.ev_charging", "sensors"]
