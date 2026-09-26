"""Tests for the Papouch sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.components.papouch.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_sensor_entity(
    hass: HomeAssistant,
    mock_config_entry,
    mock_papouch_client,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reading data and attributes from the sensor."""
    _, _, mock_device = mock_papouch_client

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mac = "00:11:22:33:44:55"

    # --- SENSOR TEST ---
    sensor_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mac}_temperature_1"
    )
    assert sensor_id is not None

    state = hass.states.get(sensor_id)
    assert state
    assert state.state == "22.5"
    assert state.attributes["unit_of_measurement"] == "°C"

    mock_device.parse_fresh_data = AsyncMock(
        return_value={
            "temperature": {"1": 24.0},
            "input": {"1": 1},
            "switch": {"1": 1},
        }
    )

    await mock_config_entry.runtime_data.async_request_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(sensor_id)
    assert state.state == "24.0"
