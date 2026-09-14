"""Test the Rabbit Air sensor platform."""

from unittest.mock import patch

import pytest
from rabbitair import Quality

from homeassistant.components.rabbitair.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_config_flow import (
    TEST_HOST,
    TEST_MAC,
    TEST_TITLE,
    TEST_TOKEN,
    TEST_UNIQUE_ID,
    get_mock_state,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
            CONF_MAC: TEST_MAC,
        },
        title=TEST_TITLE,
        unique_id=TEST_UNIQUE_ID,
    )
    entry.add_to_hass(hass)
    return entry


async def test_air_quality_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the air quality sensor."""
    with patch(
        "homeassistant.components.rabbitair.coordinator.Client.get_state",
        return_value=get_mock_state(quality=Quality.High),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.rabbit_air_air_quality")
    assert state
    assert state.state == "high"

    registry_entry = entity_registry.async_get("sensor.rabbit_air_air_quality")
    assert registry_entry
    assert registry_entry.unique_id == f"{TEST_UNIQUE_ID}_air_quality"


async def test_no_air_quality_sensor_when_quality_is_none(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the air quality sensor is not created when quality is unavailable."""
    with patch(
        "homeassistant.components.rabbitair.coordinator.Client.get_state",
        return_value=get_mock_state(quality=None),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.rabbit_air_air_quality") is None
