#!/usr/bin/env python3
"""Test script for Nederlandse Spoorwegen integration."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.nederlandse_spoorwegen.sensor import (
    NSServiceSensor,
    NSTripSensor,
)

# Add the core directory to the path
sys.path.insert(0, "/workspaces/core")

from homeassistant.components.nederlandse_spoorwegen import NSDataUpdateCoordinator
from homeassistant.const import CONF_API_KEY

# Mock the ns_api module before any imports
mock_nsapi_module = MagicMock()
mock_nsapi_class = MagicMock()
mock_nsapi_module.NSAPI = mock_nsapi_class
sys.modules["ns_api"] = mock_nsapi_module


async def test_integration():
    """Test the basic setup of the integration."""

    # Create mock objects
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()

    mock_entry = MagicMock()
    mock_entry.data = {CONF_API_KEY: "test_api_key"}
    mock_entry.options = {}
    mock_entry.entry_id = "test_entry_id"

    # Mock NSAPI instance
    mock_nsapi_instance = MagicMock()
    mock_nsapi_instance.get_stations.return_value = [MagicMock(code="AMS")]
    mock_nsapi_class.return_value = mock_nsapi_instance

    try:
        # Test coordinator creation
        coordinator = NSDataUpdateCoordinator(hass, mock_nsapi_instance, mock_entry)

        # Test service sensor creation
        service_sensor = NSServiceSensor(coordinator, mock_entry)
        assert service_sensor.unique_id == "test_entry_id_service"

        # Test trip sensor creation
        test_route = {"name": "Test Route", "from": "AMS", "to": "UTR"}
        trip_sensor = NSTripSensor(
            coordinator, mock_entry, test_route, "test_route_key"
        )
        assert trip_sensor.name == "Test Route"
    except AssertionError:
        return False
    else:
        return True


if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)
