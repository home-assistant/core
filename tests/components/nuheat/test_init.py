"""NuHeat component tests."""

from unittest.mock import Mock, patch

from homeassistant.components.nuheat.const import (
    CONF_FLOOR_AREA,
    CONF_WATT_DENSITY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .mocks import (
    MOCK_CONFIG_ENTRY,
    _create_mock_energy_usage,
    _get_mock_nuheat,
    _get_mock_thermostat_run,
)

from tests.common import MockConfigEntry

VALID_CONFIG = {
    "nuheat": {"username": "warm", "password": "feet", "devices": "thermostat123"}
}
INVALID_CONFIG = {"nuheat": {"username": "warm", "password": "feet"}}


async def test_init_success(hass: HomeAssistant) -> None:
    """Test that we can setup with valid config."""
    mock_thermostat = _get_mock_thermostat_run()
    mock_nuheat = _get_mock_nuheat(get_thermostat=mock_thermostat)

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that both climate and sensor entities are created
    state = hass.states.get("climate.master_bathroom")
    assert state is not None

    # Check heating time sensor (underscore naming convention)
    heating_time_state = hass.states.get("sensor.master_bathroom_heating_time")
    assert heating_time_state is not None
    assert int(heating_time_state.state) == 210  # 120 + 90

    # Check energy sensor
    energy_state = hass.states.get("sensor.master_bathroom_energy")
    assert energy_state is not None
    assert float(energy_state.state) == 2.6  # 1.5 + 1.1


async def test_init_energy_api_no_kwh_data(hass: HomeAssistant) -> None:
    """Test that energy sensor is not created when API returns no kWh data."""
    mock_thermostat = _get_mock_thermostat_run()
    # Override the mock to return no kWh data (user hasn't configured watt density)
    mock_thermostat.get_energy_usage = Mock(
        return_value=_create_mock_energy_usage(heating_minutes=120, energy_kwh=None)
    )
    mock_nuheat = _get_mock_nuheat(get_thermostat=mock_thermostat)

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Heating time sensor should still be created
    heating_time_state = hass.states.get("sensor.master_bathroom_heating_time")
    assert heating_time_state is not None
    assert int(heating_time_state.state) == 120

    # Energy sensor should not be created (no kWh data)
    energy_state = hass.states.get("sensor.master_bathroom_energy")
    assert energy_state is None


async def test_init_energy_calculated_from_options(hass: HomeAssistant) -> None:
    """Test that energy is calculated from floor area when configured."""
    mock_thermostat = _get_mock_thermostat_run()
    # Override the mock to return 60 minutes and no kWh data
    mock_thermostat.get_energy_usage = Mock(
        return_value=_create_mock_energy_usage(heating_minutes=60, energy_kwh=None)
    )
    mock_nuheat = _get_mock_nuheat(get_thermostat=mock_thermostat)

    with patch(
        "homeassistant.components.nuheat.nuheat.NuHeat",
        return_value=mock_nuheat,
    ):
        # Configure options for energy calculation
        # 100 sqft * 12 watts/sqft = 1200 watts
        # 1200 watts * 60 minutes / 60 / 1000 = 1.2 kWh
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG_ENTRY,
            options={CONF_FLOOR_AREA: 100.0, CONF_WATT_DENSITY: 12.0},
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Energy sensor should be created with calculated value
    energy_state = hass.states.get("sensor.master_bathroom_energy")
    assert energy_state is not None
    assert float(energy_state.state) == 1.2  # Calculated from floor area

    # Heating time should also be present
    heating_time_state = hass.states.get("sensor.master_bathroom_heating_time")
    assert heating_time_state is not None
    assert int(heating_time_state.state) == 60
