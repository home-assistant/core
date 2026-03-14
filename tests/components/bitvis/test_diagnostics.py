"""Tests for the Bitvis Power Hub diagnostics platform."""

from bitvis_protobuf import powerhub_pb2
import pytest

from homeassistant.components.bitvis.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics when no data has been received."""
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["config_entry"]["host"] == "192.168.1.100"
    assert result["config_entry"]["port"] == 5000
    assert result["coordinator"]["has_sample_data"] is False
    assert result["coordinator"]["has_diagnostic_data"] is False
    assert "device_diagnostic" not in result


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_with_diagnostic_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics output when diagnostic data is available."""
    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 500
    payload.diagnostic.wifi_rssi_dbm = -70
    coordinator.async_set_diagnostic_data(payload.diagnostic)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["coordinator"]["has_diagnostic_data"] is True
    assert result["device_diagnostic"]["uptime_s"] == 500
    assert result["device_diagnostic"]["wifi_rssi_dbm"] == -70


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_with_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that device_info fields are included in diagnostics output."""
    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 1
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    payload.diagnostic.device_info.model_name = "PowerHub"
    payload.diagnostic.device_info.sw_version = "1.0"
    coordinator.async_set_diagnostic_data(payload.diagnostic)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "device_info" in result
    assert result["device_info"]["mac_address"] == "aabbccddeeff"
    assert result["device_info"]["model_name"] == "PowerHub"
