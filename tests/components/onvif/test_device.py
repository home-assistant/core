"""Tests for the ONVIF device module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from onvif.exceptions import ONVIFError
import pytest

from homeassistant.components.onvif.const import DOMAIN
from homeassistant.components.onvif.device import ONVIFDevice
from homeassistant.components.onvif.models import Capabilities
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _create_onvif_device(hass: HomeAssistant) -> ONVIFDevice:
    """Create an ONVIF device with a mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="unique-id",
        data={
            CONF_NAME: "Test Camera",
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    config_entry.add_to_hass(hass)
    return ONVIFDevice(hass, config_entry)


async def test_get_capabilities_deviceio_service_capabilities(
    hass: HomeAssistant,
) -> None:
    """Test DeviceIO relay outputs detected via service capabilities."""
    device = _create_onvif_device(hass)

    media_service = AsyncMock()
    media_service.GetServiceCapabilities = AsyncMock(
        return_value=MagicMock(SnapshotUri=True)
    )
    imaging_service = AsyncMock()
    deviceio_service = AsyncMock()
    deviceio_service.GetServiceCapabilities = AsyncMock(
        return_value=MagicMock(RelayOutputs="3")
    )
    deviceio_service.GetRelayOutputs = AsyncMock()

    device.device = MagicMock(
        create_media_service=AsyncMock(return_value=media_service),
        get_definition=MagicMock(),
        create_imaging_service=AsyncMock(return_value=imaging_service),
        create_deviceio_service=AsyncMock(return_value=deviceio_service),
    )

    capabilities = await device.async_get_capabilities()

    assert capabilities.deviceio
    assert capabilities.relay_outputs == 3
    assert capabilities.snapshot
    assert capabilities.ptz
    assert capabilities.imaging
    deviceio_service.GetServiceCapabilities.assert_awaited_once()
    deviceio_service.GetRelayOutputs.assert_not_called()


async def test_get_capabilities_deviceio_relay_outputs_fallback(
    hass: HomeAssistant,
) -> None:
    """Test relay outputs fallback when capabilities call fails."""
    device = _create_onvif_device(hass)

    media_service = AsyncMock()
    media_service.GetServiceCapabilities = AsyncMock(return_value=None)
    imaging_service = AsyncMock()
    relay_response = MagicMock()
    relay_response.RelayOutput = [MagicMock(), MagicMock()]
    deviceio_service = AsyncMock()
    deviceio_service.GetServiceCapabilities = AsyncMock(
        side_effect=ONVIFError("capabilities error")
    )
    deviceio_service.GetRelayOutputs = AsyncMock(return_value=relay_response)

    device.device = MagicMock(
        create_media_service=AsyncMock(return_value=media_service),
        get_definition=MagicMock(),
        create_imaging_service=AsyncMock(return_value=imaging_service),
        create_deviceio_service=AsyncMock(return_value=deviceio_service),
    )

    capabilities = await device.async_get_capabilities()

    assert capabilities.deviceio
    assert capabilities.relay_outputs == 2
    deviceio_service.GetRelayOutputs.assert_awaited_once()


async def test_get_relay_outputs(hass: HomeAssistant) -> None:
    """Test relay outputs retrieval from DeviceIO."""
    device = _create_onvif_device(hass)
    device.capabilities = Capabilities(deviceio=True)

    relay_output = MagicMock()
    deviceio_service = AsyncMock()
    deviceio_service.GetRelayOutputs = AsyncMock(
        return_value=MagicMock(RelayOutput=relay_output)
    )

    device.device = MagicMock(
        create_deviceio_service=AsyncMock(return_value=deviceio_service),
    )

    relays = await device.async_get_relay_outputs()

    assert relays == [relay_output]
    deviceio_service.GetRelayOutputs.assert_awaited_once()


async def test_get_relay_outputs_error(hass: HomeAssistant) -> None:
    """Test relay outputs retrieval returns empty list on error."""
    device = _create_onvif_device(hass)
    device.capabilities = Capabilities(deviceio=True)

    deviceio_service = AsyncMock()
    deviceio_service.GetRelayOutputs = AsyncMock(side_effect=ONVIFError("boom"))

    device.device = MagicMock(
        create_deviceio_service=AsyncMock(return_value=deviceio_service),
    )

    relays = await device.async_get_relay_outputs()

    assert relays == []
    deviceio_service.GetRelayOutputs.assert_awaited_once()


async def test_get_relay_outputs_without_deviceio(hass: HomeAssistant) -> None:
    """Test relay outputs retrieval when DeviceIO unsupported."""
    device = _create_onvif_device(hass)
    device.capabilities = Capabilities(deviceio=False)

    assert await device.async_get_relay_outputs() == []


async def test_set_relay_output_state(hass: HomeAssistant) -> None:
    """Test setting relay output state uses Device service."""
    device = _create_onvif_device(hass)
    device.capabilities = Capabilities(deviceio=True)

    request = MagicMock()
    device_service = MagicMock()
    device_service.create_type.return_value = request
    device_service.SetRelayOutputState = AsyncMock()

    device.device = MagicMock(devicemgmt=device_service)

    await device.async_set_relay_output_state("relay-token", "active")

    device_service.create_type.assert_called_once_with("SetRelayOutputState")
    assert request.RelayOutputToken == "relay-token"
    assert request.LogicalState == "active"
    device_service.SetRelayOutputState.assert_awaited_once_with(request)


async def test_set_relay_output_state_without_deviceio(hass: HomeAssistant) -> None:
    """Test setting relay output state raises when DeviceIO unsupported."""
    device = _create_onvif_device(hass)
    device.capabilities = Capabilities(deviceio=False)
    device.device = MagicMock(devicemgmt=MagicMock())

    with pytest.raises(ONVIFError):
        await device.async_set_relay_output_state("relay-token", "active")
