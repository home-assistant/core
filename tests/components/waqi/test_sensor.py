"""Test the World Air Quality Index (WAQI) sensor."""

import json
from unittest.mock import patch

from aiowaqi import WAQIAirQuality, WAQIError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.waqi.const import DOMAIN
from homeassistant.components.waqi.sensor import SENSORS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test failed update."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        return_value=WAQIAirQuality.from_dict(
            json.loads(load_fixture("waqi/air_quality_sensor.json"))
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    for sensor in SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"4584_{sensor.key}"
        )
        assert hass.states.get(entity_id) == snapshot


async def test_updating_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test failed update."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "aiowaqi.WAQIClient.get_by_station_number",
        side_effect=WAQIError(),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
