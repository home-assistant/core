"""Tests for hassfest mdi_icons validation."""

from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

from script.hassfest.mdi_icons import validate
from script.hassfest.model import Config, Integration

PINNED_VERSION = "20260729.7"


def _create_frontend_integration(config: Config) -> dict[str, Integration]:
    """Create the frontend integration pinning a frontend version."""
    integration = Integration(
        config.core_integrations_path / "frontend", _config=config
    )
    integration._manifest = {
        "domain": "frontend",
        "name": "Home Assistant Frontend",
        "requirements": [f"home-assistant-frontend=={PINNED_VERSION}"],
    }
    return {"frontend": integration}


def test_outdated_environment(config: Config) -> None:
    """Test validation is skipped when the installed frontend is not the pinned one."""
    integrations = _create_frontend_integration(config)

    with patch("script.hassfest.mdi_icons.version", return_value="20250101.0"):
        validate(integrations, config)

    assert not config.errors
    # Without the icons of the pinned version, the file must not be regenerated
    assert "mdi_icons_content" not in config.cache


def test_frontend_not_installed(config: Config) -> None:
    """Test validation is skipped when the frontend is not installed."""
    integrations = _create_frontend_integration(config)

    with patch("script.hassfest.mdi_icons.version", side_effect=PackageNotFoundError):
        validate(integrations, config)

    assert not config.errors
    assert "mdi_icons_content" not in config.cache


def test_matching_environment(config: Config) -> None:
    """Test the file is generated when the installed frontend matches the pin."""
    integrations = _create_frontend_integration(config)

    with (
        patch("script.hassfest.mdi_icons.version", return_value=PINNED_VERSION),
        patch("script.hassfest.mdi_icons._load_mdi_icons", return_value={"account"}),
    ):
        validate(integrations, config)

    assert PINNED_VERSION in config.cache["mdi_icons_content"]
