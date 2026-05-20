"""Test ONVIF PTZ capabilities."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _build_onvif_test_objects():
    """Build common ONVIF mock objects for PTZ service tests."""
    ptz_service = MagicMock()
    ptz_service.ContinuousMove = AsyncMock()
    ptz_service.Stop = AsyncMock()
    ptz_service.GetPresets = AsyncMock()

    media_service = MagicMock()
    media_service.GetServiceCapabilities = AsyncMock()
    media_service.GetProfiles = AsyncMock(
        return_value=[
            SimpleNamespace(
                token="profile_token",
                Name="MainStream",
                VideoEncoderConfiguration=SimpleNamespace(
                    Resolution=SimpleNamespace(Width=1920, Height=1080),
                    Encoding="H264",
                ),
                VideoSourceConfiguration=MagicMock(),
                PTZConfiguration=MagicMock(),
            )
        ]
    )

    devicemgmt_service = MagicMock()
    devicemgmt_service.GetSystemDateAndTime = AsyncMock()
    devicemgmt_service.GetNetworkInterfaces = AsyncMock()
    devicemgmt_service.GetDeviceInformation = AsyncMock(
        return_value=SimpleNamespace(
            Manufacturer="Mock",
            Model="MockCam",
            FirmwareVersion="1.0",
            SerialNumber="123",
            HardwareId="abc",
        )
    )

    onvif_capabilities = {
        "Media": {"XAddr": "http://media"},
        "PTZ": {"XAddr": "http://ptz"},
        "Imaging": {"XAddr": "http://imaging"},
        "Events": {
            "XAddr": None,
            "WSPullPointSupport": False,
            "WSSubscriptionPolicySupport": False,
        },
    }

    imaging_service = MagicMock()

    mock_camera = MagicMock()
    mock_camera.xaddrs = {}
    mock_camera.update_xaddrs = AsyncMock()
    mock_camera.close = AsyncMock()
    mock_camera.get_capabilities = AsyncMock(return_value=onvif_capabilities)
    mock_camera.create_devicemgmt_service = AsyncMock(return_value=devicemgmt_service)
    mock_camera.create_media_service = AsyncMock(return_value=media_service)
    mock_camera.create_ptz_service = AsyncMock(return_value=ptz_service)
    mock_camera.create_imaging_service = AsyncMock(return_value=imaging_service)
    mock_camera.create_pullpoint_manager = AsyncMock(return_value=MagicMock())
    mock_camera.get_snapshot = AsyncMock(return_value=False)

    entry = MockConfigEntry(
        domain="onvif",
        title="Mock Title",
        unique_id="test-onvif-unique-id",
        data={
            CONF_NAME: "Mock Title",
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )

    return entry, mock_camera, ptz_service


async def test_ptz_continuous_move_calls_stop_when_duration_nonzero(
    hass: HomeAssistant,
) -> None:
    """Test ONVIF PTZ ContinuousMove calls Stop when duration is nonzero."""
    entry, mock_camera, ptz_service = _build_onvif_test_objects()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onvif.device.ONVIFCamera",
            return_value=mock_camera,
        ),
        patch(
            "homeassistant.components.onvif.device.asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep,
        patch(
            "homeassistant.components.onvif.device.ONVIFDevice.async_start_events",
            new=AsyncMock(return_value=False),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_sleep.reset_mock()

        await hass.services.async_call(
            "onvif",
            "ptz",
            {
                "entity_id": "camera.mock_title_mainstream",
                "move_mode": "ContinuousMove",
                "pan": "LEFT",
                "tilt": "DOWN",
                "speed": 1,
                "distance": 1,
                "continuous_duration": 1,
            },
            blocking=True,
        )

    ptz_service.ContinuousMove.assert_awaited_once()
    ptz_service.Stop.assert_awaited_once()
    mock_sleep.assert_awaited_once_with(1)


async def test_ptz_continuous_move_does_not_call_stop_when_duration_zero(
    hass: HomeAssistant,
) -> None:
    """Test ONVIF PTZ ContinuousMove does not call Stop when duration is zero."""
    entry, mock_camera, ptz_service = _build_onvif_test_objects()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onvif.device.ONVIFCamera",
            return_value=mock_camera,
        ),
        patch(
            "homeassistant.components.onvif.device.asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep,
        patch(
            "homeassistant.components.onvif.device.ONVIFDevice.async_start_events",
            new=AsyncMock(return_value=False),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_sleep.reset_mock()

        await hass.services.async_call(
            "onvif",
            "ptz",
            {
                "entity_id": "camera.mock_title_mainstream",
                "move_mode": "ContinuousMove",
                "pan": "LEFT",
                "tilt": "DOWN",
                "speed": 1,
                "distance": 1,
                "continuous_duration": 0,
            },
            blocking=True,
        )

    ptz_service.ContinuousMove.assert_awaited_once()
    ptz_service.Stop.assert_not_called()
    mock_sleep.assert_not_awaited()
