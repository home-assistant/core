"""Test ONVIF PTZ capabilities."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import HOST, MAC, NAME, PASSWORD, PORT, USERNAME, setup_mock_onvif_camera

from tests.common import MockConfigEntry


def _setup_ptz_camera_mocks(mock_onvif_camera_cls: MagicMock) -> MagicMock:
    """Configure the patched ONVIFCamera class for PTZ tests.

    Uses the shared ``setup_mock_onvif_camera`` full-setup helper and only adds
    the PTZ service mocks the tests assert against, returning the ptz_service
    mock so callers can check ContinuousMove/Stop calls.
    """
    setup_mock_onvif_camera(mock_onvif_camera_cls, with_full_setup=True)

    ptz_service = mock_onvif_camera_cls.create_ptz_service.return_value
    ptz_service.ContinuousMove = AsyncMock()
    ptz_service.Stop = AsyncMock()
    return ptz_service


def _make_entry() -> MockConfigEntry:
    """Build a config entry suitable for the PTZ tests."""
    return MockConfigEntry(
        domain="onvif",
        title=NAME,
        unique_id=MAC,
        data={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )


async def _call_ptz(hass: HomeAssistant, continuous_duration: float) -> None:
    """Call the onvif.ptz service with the given continuous_duration."""
    await hass.services.async_call(
        "onvif",
        "ptz",
        {
            "entity_id": "camera.testcamera_mainstream",
            "move_mode": "ContinuousMove",
            "pan": "LEFT",
            "tilt": "DOWN",
            "speed": 1,
            "distance": 1,
            "continuous_duration": continuous_duration,
        },
        blocking=True,
    )


async def test_ptz_continuous_move_calls_stop_when_duration_nonzero(
    hass: HomeAssistant,
) -> None:
    """Test ONVIF PTZ ContinuousMove calls Stop when duration is nonzero."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onvif.device.ONVIFCamera"
        ) as mock_onvif_camera_cls,
        patch(
            "homeassistant.components.onvif.device.asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep,
    ):
        ptz_service = _setup_ptz_camera_mocks(mock_onvif_camera_cls)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_sleep.reset_mock()

        await _call_ptz(hass, continuous_duration=1)

    ptz_service.ContinuousMove.assert_awaited_once()
    ptz_service.Stop.assert_awaited_once()
    mock_sleep.assert_awaited_once_with(1)


async def test_ptz_continuous_move_does_not_call_stop_when_duration_zero(
    hass: HomeAssistant,
) -> None:
    """Test ONVIF PTZ ContinuousMove does not call Stop when duration is zero."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onvif.device.ONVIFCamera"
        ) as mock_onvif_camera_cls,
        patch(
            "homeassistant.components.onvif.device.asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep,
    ):
        ptz_service = _setup_ptz_camera_mocks(mock_onvif_camera_cls)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_sleep.reset_mock()

        await _call_ptz(hass, continuous_duration=0)

    ptz_service.ContinuousMove.assert_awaited_once()
    ptz_service.Stop.assert_not_awaited()
    mock_sleep.assert_not_awaited()
