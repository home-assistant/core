"""Tests for the srp_energy sensor platform."""
from unittest.mock import patch

import pytest
from requests.models import HTTPError

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_loading_sensors(hass: HomeAssistant, init_integration) -> None:
    """Test the srp energy sensors."""
    # Validate the Config Entry was initialized
    assert init_integration.state == ConfigEntryState.LOADED

    # Check sensors were loaded
    assert len(hass.states.async_all()) == 1


async def test_srp_entity(hass: HomeAssistant, init_integration) -> None:
    """Test the SrpEntity."""
    usage_state = hass.states.get("sensor.srp_energy_total_usage")
    assert usage_state.state == "150.8"

    # Validate attributions
    assert (
        usage_state.attributes.get("state_class") is SensorStateClass.TOTAL_INCREASING
    )
    assert usage_state.attributes.get(ATTR_ATTRIBUTION) == "Powered by SRP Energy"
    assert (
        usage_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.KILO_WATT_HOUR
    )

    assert usage_state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY


@pytest.mark.parametrize("error", [TimeoutError, HTTPError])
async def test_srp_entity_update_failed(
    hass: HomeAssistant,
    error: Exception,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the SrpEntity."""

    with patch(
        "homeassistant.components.srp_energy.SrpEnergyClient", autospec=True
    ) as srp_energy_mock:
        client = srp_energy_mock.return_value
        client.validate.return_value = True
        client.usage.side_effect = error
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    usage_state = hass.states.get("sensor.home_energy_usage")
    assert usage_state is None
