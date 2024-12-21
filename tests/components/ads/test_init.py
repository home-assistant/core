"""Test the ADS initialization."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pyads
import pytest

from homeassistant.components.ads import (
    DATA_ADS,
    DOMAIN,
    async_setup,
    async_setup_ads_integration,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.ads.config_flow import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant instance."""
    mock_hass = Mock(spec=HomeAssistant)
    mock_hass.services = MagicMock()
    mock_hass.services.async_call = AsyncMock()
    mock_hass.data = {}
    mock_hass.bus = MagicMock()
    mock_hass.bus.async_listen = AsyncMock()
    return mock_hass


@pytest.fixture
def mock_client():
    """Mock ADS client."""
    return Mock()


@pytest.fixture
def mock_ads_hub():
    """Mock AdsHub instance."""
    return Mock()


@pytest.fixture
def mock_service_call():
    """Mock ServiceCall."""
    return Mock(ServiceCall)


@pytest.fixture
def config_entry():
    """Create and return a mock ConfigEntry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="ADS",
        data={
            CONF_DEVICE: "192.168.10.120.1.1",
            CONF_PORT: 851,
            CONF_IP_ADDRESS: "192.168.1.100",
        },
        source="user",
        entry_id="test_entry",
        unique_id="test_unique_id",  # unique ID for this entry
        minor_version=0,  # optional minor version, defaulting to 0
        options={},  # any additional options (use an empty dict if none)
        discovery_keys=None,  # set to None if no discovery keys are needed
    )


@pytest.mark.asyncio  # Ensures the tests are run asynchronously
class TestADSComponent:
    """Test the ADS component setup and configuration."""

    @patch(
        "homeassistant.components.ads.async_setup_ads_integration", return_value=True
    )
    async def test_async_setup_no_config(self, mock_setup_ads_integration, mock_hass):
        """async_setup should return True when no YAML config is provided."""
        config = {}
        result = await async_setup(mock_hass, config)
        assert result is True
        mock_setup_ads_integration.assert_not_called()

    @patch(
        "homeassistant.components.ads.async_setup_ads_integration", return_value=True
    )
    async def test_async_setup_entry(
        self, mock_setup_ads_integration, mock_hass, config_entry
    ):
        """async_setup_entry should call async_setup_ads_integration."""
        result = await async_setup_entry(mock_hass, config_entry)
        assert result is True
        mock_setup_ads_integration.assert_called_once_with(mock_hass, config_entry.data)

    @patch("pyads.Connection", return_value=Mock())
    @patch("homeassistant.components.ads.AdsHub", return_value=Mock())
    async def test_async_setup_ads_integration_success(
        self, mock_ads_hub, mock_pyads_connection, mock_hass
    ):
        """async_setup_ads_integration should handle successful setup."""
        config = {CONF_DEVICE: "192.168.10.10.1.1", CONF_PORT: 12345}
        result = await async_setup_ads_integration(mock_hass, config)
        assert result is True
        mock_pyads_connection.assert_called_once()
        mock_ads_hub.assert_called_once()
        assert DATA_ADS in mock_hass.data
        mock_hass.bus.async_listen.assert_called_once()

    @patch("pyads.Connection", side_effect=pyads.ADSError)
    async def test_async_setup_ads_integration_failure(
        self, mock_pyads_connection, mock_hass
    ):
        """async_setup_ads_integration should handle connection errors."""
        config = {CONF_DEVICE: "TestDevice", CONF_PORT: 12345}
        result = await async_setup_ads_integration(mock_hass, config)
        assert result is False
        mock_pyads_connection.assert_called_once()

    @patch("homeassistant.components.ads.AdsHub.shutdown")
    async def test_async_unload_entry_success(
        self, mock_shutdown, mock_hass, config_entry
    ):
        """async_unload_entry should unload ADS data successfully."""
        ads_hub_mock = Mock()
        mock_hass.data[DATA_ADS] = ads_hub_mock
        result = await async_unload_entry(mock_hass, config_entry)
        assert result is True
        ads_hub_mock.shutdown.assert_called_once()

    async def test_async_unload_entry_no_ads_data(self, mock_hass, config_entry):
        """async_unload_entry should log and return False if no ADS data found."""
        result = await async_unload_entry(mock_hass, config_entry)
        assert result is False

    @patch("homeassistant.components.ads.AdsHub.shutdown", side_effect=pyads.ADSError)
    async def test_async_unload_entry_shutdown_failure(
        self, mock_shutdown, mock_hass, config_entry
    ):
        """async_unload_entry should log and return False if shutdown fails."""
        ads_hub_mock = Mock()
        ads_hub_mock.shutdown.side_effect = pyads.ADSError("Shutdown error")
        mock_hass.data[DATA_ADS] = ads_hub_mock
        result = await async_unload_entry(mock_hass, config_entry)
        assert result is False
        ads_hub_mock.shutdown.assert_called_once()
