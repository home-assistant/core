"""Tests for the system info helper."""

import json
import os
from unittest.mock import patch

import pytest

from homeassistant.components import hassio
from homeassistant.const import __version__ as current_version
from homeassistant.core import HomeAssistant
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.system_info import async_get_system_info


async def test_get_system_info(hass: HomeAssistant) -> None:
    """Test the get system info."""
    info = await async_get_system_info(hass)
    assert isinstance(info, dict)
    assert info["version"] == current_version
    assert info["user"] is not None
    assert json.dumps(info) is not None


async def test_get_system_info_supervisor_not_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the get system info when supervisor is not available."""
    hass.config.components.add("hassio")
    assert is_hassio(hass) is True
    with (
        patch("platform.system", return_value="Linux"),
        patch("homeassistant.helpers.system_info.is_docker_env", return_value=True),
        patch("homeassistant.helpers.system_info.is_official_image", return_value=True),
        patch("homeassistant.helpers.hassio.is_hassio", return_value=True),
        patch.object(hassio, "get_info", return_value=None),
        patch("homeassistant.helpers.system_info.cached_get_user", return_value="root"),
    ):
        info = await async_get_system_info(hass)
        assert isinstance(info, dict)
        assert info["version"] == current_version
        assert info["user"] is not None
        assert json.dumps(info) is not None
        assert info["installation_type"] == "Home Assistant Supervised"
        assert "No Home Assistant Supervisor info available" in caplog.text


async def test_get_system_info_supervisor_not_loaded(hass: HomeAssistant) -> None:
    """Test the get system info when supervisor is not loaded."""
    assert is_hassio(hass) is False
    with (
        patch("platform.system", return_value="Linux"),
        patch("homeassistant.helpers.system_info.is_docker_env", return_value=True),
        patch("homeassistant.helpers.system_info.is_official_image", return_value=True),
        patch.object(hassio, "get_info", return_value=None),
        patch.dict(os.environ, {"SUPERVISOR": "127.0.0.1"}),
    ):
        info = await async_get_system_info(hass)
        assert isinstance(info, dict)
        assert info["version"] == current_version
        assert info["user"] is not None
        assert json.dumps(info) is not None
        assert info["installation_type"] == "Unsupported Third Party Container"


@pytest.mark.parametrize(
    ("is_docker_env", "is_official", "is_venv", "user", "expected_installation_type"),
    [
        # Docker environment true, venv flag is ignored in this case
        (True, True, True, "root", "Home Assistant Container"),
        (True, True, True, "user", "Unsupported Third Party Container"),
        (True, False, True, "root", "Unsupported Third Party Container"),
        (True, False, True, "user", "Unsupported Third Party Container"),
        (True, True, False, "root", "Home Assistant Container"),
        (True, True, False, "user", "Unsupported Third Party Container"),
        (True, False, False, "root", "Unsupported Third Party Container"),
        (True, False, False, "user", "Unsupported Third Party Container"),
        # Docker environment false, unknown if not venv, otherwise Home Assistant Core
        (False, True, True, "root", "Home Assistant Core"),
        (False, True, True, "user", "Home Assistant Core"),
        (False, False, True, "root", "Home Assistant Core"),
        (False, False, True, "user", "Home Assistant Core"),
        (False, True, False, "root", "Unknown"),
        (False, True, False, "user", "Unknown"),
        (False, False, False, "root", "Unknown"),
        (False, False, False, "user", "Unknown"),
    ],
)
async def test_non_hassio_installation_type(
    hass: HomeAssistant,
    user: str,
    is_docker_env: bool,
    is_official: bool,
    is_venv: bool,
    expected_installation_type: str,
) -> None:
    """Test non-Hass.io installation types."""
    assert is_hassio(hass) is False
    with (
        patch("platform.system", return_value="Linux"),
        patch(
            "homeassistant.helpers.system_info.is_docker_env",
            return_value=is_docker_env,
        ),
        patch(
            "homeassistant.helpers.system_info.is_official_image",
            return_value=is_official,
        ),
        patch(
            "homeassistant.helpers.system_info.is_virtual_env",
            return_value=is_venv,
        ),
        patch("homeassistant.helpers.system_info.cached_get_user", return_value=user),
        patch(
            "homeassistant.helpers.system_info.async_get_container_arch",
            return_value="aarch64",
        ),
    ):
        info = await async_get_system_info(hass)
        assert info["installation_type"] == expected_installation_type


@pytest.mark.parametrize("error", [KeyError, OSError])
async def test_getuser_oserror(hass: HomeAssistant, error: Exception) -> None:
    """Test getuser oserror."""
    with patch("homeassistant.helpers.system_info.cached_get_user", side_effect=error):
        info = await async_get_system_info(hass)
        assert info["user"] is None
