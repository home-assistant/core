"""Tests for the quantum_gateway device tracker."""

from unittest.mock import AsyncMock

import pytest
from requests import RequestException

from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.components.device_tracker.test_init import mock_yaml_devices  # noqa: F401


@pytest.mark.usefixtures("yaml_devices")
async def test_get_scanner(hass: HomeAssistant, mock_scanner: AsyncMock) -> None:
    """Test creating a quantum gateway scanner."""
    await setup_platform(hass)

    device_1 = hass.states.get("device_tracker.desktop")
    assert device_1 is not None
    assert device_1.state == STATE_HOME

    device_2 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
    assert device_2 is not None
    assert device_2.state == STATE_HOME


@pytest.mark.usefixtures("yaml_devices")
async def test_get_scanner_error(hass: HomeAssistant, mock_scanner: AsyncMock) -> None:
    """Test failure when creating a quantum gateway scanner."""
    mock_scanner.side_effect = RequestException("Error")
    await setup_platform(hass)

    assert "quantum_gateway.device_tracker" not in hass.config.components


@pytest.mark.usefixtures("yaml_devices")
async def test_scan_devices_error(hass: HomeAssistant, mock_scanner: AsyncMock) -> None:
    """Test failure when scanning devices."""
    mock_scanner.return_value.scan_devices.side_effect = RequestException("Error")
    await setup_platform(hass)

    assert "quantum_gateway.device_tracker" in hass.config.components

    device_1 = hass.states.get("device_tracker.desktop")
    assert device_1 is None

    device_2 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
    assert device_2 is None
