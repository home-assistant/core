"""Tests for WiiM diagnostics."""

import pytest
from unittest.mock import AsyncMock

from wiim.models import WiimDeviceDiagnostics

from homeassistant.components.wiim.diagnostics import async_get_config_entry_diagnostics
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_config_entry_diagnostics_redacts_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
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

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert diagnostics["device"]["name"] == "Test WiiM Device"
    assert diagnostics["device"]["udn"] == "**REDACTED**"
    assert diagnostics["device"]["ip_address"] == "**REDACTED**"
    assert diagnostics["device"]["model_name"] == "WiiM Pro"
    assert diagnostics["device"]["supports_http_api"] is True
    assert diagnostics["multiroom"]["role"] == "standalone"
    assert diagnostics["multiroom"]["leader_udn"] == "**REDACTED**"
    assert diagnostics["multiroom"]["member_udns"] == "**REDACTED**"
