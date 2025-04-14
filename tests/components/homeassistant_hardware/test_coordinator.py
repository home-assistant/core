"""Test firmware update coordinator for Home Assistant Hardware."""

from unittest.mock import AsyncMock, Mock, call, patch

from ha_silabs_firmware_client import FirmwareManifest, ManifestMissing
import pytest
from yarl import URL

from homeassistant.components.homeassistant_hardware.coordinator import (
    FirmwareUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util


async def test_firmware_update_coordinator_fetching(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the firmware update coordinator loads manifests."""
    session = async_get_clientsession(hass)

    manifest = FirmwareManifest(
        url=URL("https://example.org/firmware"),
        html_url=URL("https://example.org/release_notes"),
        created_at=dt_util.utcnow(),
        firmwares=(),
    )

    mock_client = Mock()
    mock_client.async_update_data = AsyncMock(side_effect=[ManifestMissing(), manifest])

    with patch(
        "homeassistant.components.homeassistant_hardware.coordinator.FirmwareUpdateClient",
        return_value=mock_client,
    ):
        coordinator = FirmwareUpdateCoordinator(
            hass, session, "https://example.org/firmware"
        )

    listener = Mock()
    coordinator.async_add_listener(listener)

    # The first update will fail
    await coordinator.async_refresh()
    assert listener.mock_calls == [call()]
    assert coordinator.data is None
    assert "GitHub release assets haven't been uploaded yet" in caplog.text

    # The second will succeed
    await coordinator.async_refresh()
    assert listener.mock_calls == [call(), call()]
    assert coordinator.data == manifest

    await coordinator.async_shutdown()
