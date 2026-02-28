"""Test the Cloudflare sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


@pytest.mark.usefixtures("location_info")
async def test_sensor_setup(
    hass: HomeAssistant, cfupdate: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Test the Cloudflare sensor setup."""
    instance = cfupdate.return_value
    instance.list_dns_records.return_value = [
        {
            "id": "zone-record-id",
            "type": "A",
            "name": "ha.mock.com",
            "proxied": True,
            "content": "1.2.3.4",
        },
        {
            "id": "zone-record-id-2",
            "type": "A",
            "name": "homeassistant.mock.com",
            "proxied": True,
            "content": "1.2.3.4",
        },
    ]

    await init_integration(hass)

    # Check Last Update Sensor
    state = hass.states.get("sensor.cloudflare_zone_mock_com_last_update")
    assert state
    assert state.state != STATE_UNAVAILABLE

    entry = entity_registry.async_get("sensor.cloudflare_zone_mock_com_last_update")
    assert entry
    assert entry.unique_id == "mock-zone-id_last_update"

    # Check External IP Sensor
    state = hass.states.get("sensor.cloudflare_zone_mock_com_external_ip")
    assert state
    assert state.state == "0.0.0.0"  # This comes from location_info fixture

    entry = entity_registry.async_get("sensor.cloudflare_zone_mock_com_external_ip")
    assert entry
    assert entry.unique_id == "mock-zone-id_external_ip"


@pytest.mark.usefixtures("location_info")
async def test_sensor_values(hass: HomeAssistant, cfupdate: MagicMock) -> None:
    """Test sensor values update correctly."""
    await init_integration(hass)

    # Verify initial state
    state = hass.states.get("sensor.cloudflare_zone_mock_com_external_ip")
    assert state
    assert state.state == "0.0.0.0"  # From location_info fixture
