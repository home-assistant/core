"""Home Assistant integration-level tests for Ecobulles sensors."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ecobulles.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_sensor_setup(hass: HomeAssistant, mock_config_entry) -> None:
    """The integration loads its entities without talking to the real cloud."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ecobulles.coordinator.EcobullesClient.get_total_water_and_co2_usage",
        AsyncMock(
            return_value={
                "total_gas": 35_464_000,
                "total_eau": 161_649,
                "last_updated": "2025-06-05T21:50:00",
            }
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    water_usage_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-eco-ref_water_usage"
    )
    co2_injection_time_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-eco-ref_co2_injection_time"
    )

    assert water_usage_entity_id is not None
    assert co2_injection_time_entity_id is not None
    assert hass.states.get(water_usage_entity_id).state == "161649"
    assert hass.states.get(co2_injection_time_entity_id).state == "35464.0"
    assert [entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)] == [
        mock_config_entry.entry_id
    ]
