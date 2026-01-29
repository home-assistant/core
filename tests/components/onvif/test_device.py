"""Test ONVIF device methods."""

from unittest.mock import AsyncMock, MagicMock

from onvif.exceptions import ONVIFError
import pytest

from homeassistant.components.onvif.models import Capabilities
from homeassistant.core import HomeAssistant

from . import setup_onvif_integration


async def test_device_get_relay_outputs(hass: HomeAssistant) -> None:
    """Test getting relay outputs from device."""
    _, _, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=2)
    )

    relays = await device.async_get_relay_outputs()

    assert len(relays) == 2
    assert relays[0].token == "RelayOutputToken_0"
    assert relays[1].token == "RelayOutputToken_1"


async def test_device_set_relay_output_state(hass: HomeAssistant) -> None:
    """Test setting relay output state."""
    _, _, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=1)
    )

    # Mock the devicemgmt service (not create_device_service)
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.create_type = MagicMock(return_value=mock_req)
    mock_service.SetRelayOutputState = AsyncMock(return_value=None)
    device.device.devicemgmt = mock_service

    # Test setting active state
    await device.async_set_relay_output_state("TestToken", "active")

    mock_service.create_type.assert_called_once_with("SetRelayOutputState")
    assert mock_req.RelayOutputToken == "TestToken"
    assert mock_req.LogicalState == "active"
    mock_service.SetRelayOutputState.assert_called_once_with(mock_req)


async def test_device_set_relay_output_state_error(hass: HomeAssistant) -> None:
    """Test error handling when setting relay output state."""
    _, _, device = await setup_onvif_integration(
        hass, capabilities=Capabilities(deviceio=True, relay_outputs=1)
    )

    # Mock the devicemgmt service to raise an error
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.create_type = MagicMock(return_value=mock_req)
    mock_service.SetRelayOutputState = AsyncMock(side_effect=ONVIFError("Test error"))
    device.device.devicemgmt = mock_service

    # Should raise the error
    with pytest.raises(ONVIFError, match="Test error"):
        await device.async_set_relay_output_state("TestToken", "active")
