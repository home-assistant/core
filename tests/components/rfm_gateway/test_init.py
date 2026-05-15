"""Tests for the RFM Gateway integration init/unload flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components import rfm_gateway
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "192.0.2.10"


def _mock_caps() -> rfm_gateway.RfmCapabilities:
    """Return mocked gateway capabilities."""
    return rfm_gateway.RfmCapabilities(
        supported_frequency_ranges=[(433_050_000, 434_790_000)],
        supported_modulations=["ook"],
        device_name="RFM Gateway",
    )


async def test_load_unload_config_entry(hass: HomeAssistant) -> None:
    """Test loading and unloading the config entry."""
    entry = MockConfigEntry(
        domain=rfm_gateway.DOMAIN,
        title="RFM Gateway",
        data={rfm_gateway.CONF_HOST: TEST_HOST},
        unique_id=TEST_HOST,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rfm_gateway.radio_frequency.RfmGatewayClient.async_get_capabilities",
        new=AsyncMock(return_value=_mock_caps()),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
