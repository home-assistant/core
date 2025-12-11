"""Test Eufy Security diagnostics."""

from unittest.mock import MagicMock

from homeassistant.components.eufy_security.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
) -> None:
    """Test diagnostics returns correct data."""
    result = await async_get_config_entry_diagnostics(hass, init_integration)

    # Check config entry data is redacted
    assert "config_entry" in result
    assert result["config_entry"]["data"]["email"] == "**REDACTED**"
    assert result["config_entry"]["data"]["password"] == "**REDACTED**"

    # Check cameras data
    assert "cameras" in result
    assert mock_camera.serial in result["cameras"]
    camera_data = result["cameras"][mock_camera.serial]
    assert camera_data["name"] == mock_camera.name
    assert camera_data["model"] == mock_camera.model
    assert camera_data["serial"] == mock_camera.serial
    assert "has_ip_address" in camera_data
    assert "has_rtsp_credentials" in camera_data
    assert "has_thumbnail" in camera_data

    # Check stations data
    assert "stations" in result


async def test_diagnostics_redacts_sensitive_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics properly redacts sensitive data."""
    result = await async_get_config_entry_diagnostics(hass, init_integration)

    config_data = result["config_entry"]["data"]

    # These fields should be redacted
    for key in ("email", "password", "token", "private_key", "server_public_key"):
        if key in config_data:
            assert config_data[key] == "**REDACTED**"
