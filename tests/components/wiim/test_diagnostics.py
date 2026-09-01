"""Tests for WiiM diagnostics."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion
from wiim.models import WiimDeviceDiagnostics

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_config_entry_diagnostics_redacts_identifiers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics include safe runtime data."""
    mock_wiim_device.as_diagnostics.return_value = WiimDeviceDiagnostics(
        name="Test WiiM Device",
        udn="uuid:test-udn-1234",
        model_name="WiiM Pro",
        manufacturer="Linkplay Tech",
        firmware_version="4.8.523456",
        ip_address="192.168.1.100",
        available=True,
        supports_http_api=True,
        presentation_url_available=True,
        event_subscriptions_active=True,
        input_modes=("Line In",),
        output_modes=("Speaker Out",),
        play_mode="Network",
        output_mode="speaker",
        volume=50,
        muted=False,
    )

    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
