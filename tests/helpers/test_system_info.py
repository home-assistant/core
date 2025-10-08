"""Tests for the system info helper."""

import json
import os
from unittest.mock import patch

import pytest

from homeassistant.components import hassio
from homeassistant.const import __version__ as current_version
from homeassistant.core import HomeAssistant
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
    with (
        patch("platform.system", return_value="Linux"),
        patch("homeassistant.helpers.system_info.is_docker_env", return_value=True),
        patch("homeassistant.helpers.system_info.is_official_image", return_value=True),
        patch.object(hassio, "is_hassio", return_value=True),
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


async def test_container_installationtype(hass: HomeAssistant) -> None:
    """Test container installation type."""
    with (
        patch("platform.system", return_value="Linux"),
        patch("homeassistant.helpers.system_info.is_docker_env", return_value=True),
        patch("homeassistant.helpers.system_info.is_official_image", return_value=True),
        patch("homeassistant.helpers.system_info.cached_get_user", return_value="root"),
    ):
        info = await async_get_system_info(hass)
        assert info["installation_type"] == "Home Assistant Container"

    with (
        patch("platform.system", return_value="Linux"),
        patch("homeassistant.helpers.system_info.is_docker_env", return_value=True),
        patch(
            "homeassistant.helpers.system_info.is_official_image", return_value=False
        ),
        patch("homeassistant.helpers.system_info.cached_get_user", return_value="user"),
    ):
        info = await async_get_system_info(hass)
        assert info["installation_type"] == "Unsupported Third Party Container"


@pytest.mark.parametrize("error", [KeyError, OSError])
async def test_getuser_oserror(hass: HomeAssistant, error: Exception) -> None:
    """Test getuser oserror."""
    with patch("homeassistant.helpers.system_info.cached_get_user", side_effect=error):
        info = await async_get_system_info(hass)
        assert info["user"] is None
