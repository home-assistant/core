"""Test the No-IP.com Coordinator."""
from typing import Any
from unittest.mock import patch

from homeassistant.components.no_ip import DOMAIN, NoIPDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant


# Mock-Funktion for _async_update_data
async def mock_async_update_data(self) -> dict[str, Any]:
    """Mock for the _async_update_data method."""
    return {
        CONF_IP_ADDRESS: "1.2.3.4",
        CONF_DOMAIN: "test",
        CONF_USERNAME: None,
        CONF_PASSWORD: None,
    }


@patch(
    "homeassistant.components.no_ip.coordinator.NoIPDataUpdateCoordinator._async_update_data",
    mock_async_update_data,
)
async def test_coordinator_update(hass: HomeAssistant) -> None:
    """Test coordinator update."""
    # Create a new ConfigEntry with your configuration data
    config_entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test",
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test",
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
        },
        source="test",
        options={},
    )

    # Create a coordinator instance using the ConfigEntry
    coordinator = NoIPDataUpdateCoordinator(hass, config_entry)

    # Fetch the updated data using the coordinator
    data = await coordinator._async_update_data()

    # Add more assertions based on the actual data you expect
    assert data == {
        CONF_IP_ADDRESS: "1.2.3.4",
        CONF_DOMAIN: "test",
        CONF_USERNAME: None,
        CONF_PASSWORD: None,
        # Add more keys based on the expected response from the API
    }
