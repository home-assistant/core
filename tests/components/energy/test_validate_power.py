"""Test power stat validation."""

from unittest.mock import patch

import pytest

from homeassistant.components.energy import async_get_manager, validate
from homeassistant.components.energy.data import EnergyManager
from homeassistant.components.recorder import Recorder
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_get_metadata():
    """Mock recorder.statistics.get_metadata."""
    mocks = {}

    def _get_metadata(_hass, *, statistic_ids):
        result = {}
        for statistic_id in statistic_ids:
            if statistic_id in mocks:
                if mocks[statistic_id] is not None:
                    result[statistic_id] = mocks[statistic_id]
            else:
                result[statistic_id] = (1, {})
        return result

    with patch(
        "homeassistant.components.recorder.statistics.get_metadata",
        wraps=_get_metadata,
    ):
        yield mocks


@pytest.fixture(autouse=True)
async def mock_energy_manager(
    recorder_mock: Recorder, hass: HomeAssistant
) -> EnergyManager:
    """Set up energy."""

    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()
    return manager


async def test_validation_grid_power_valid(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating grid with valid power sensor."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "power": [
                        {
                            "stat_power": "sensor.grid_power",
                        }
                    ],
                    "cost_adjustment_day": 0.0,
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.grid_power",
        "1.5",
        {
            "device_class": "power",
            "unit_of_measurement": UnitOfPower.KILO_WATT,
            "state_class": "measurement",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
    }


async def test_validation_grid_power_wrong_unit(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating grid with power sensor having wrong unit."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "power": [
                        {
                            "stat_power": "sensor.grid_power",
                        }
                    ],
                    "cost_adjustment_day": 0.0,
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.grid_power",
        "1.5",
        {
            "device_class": "power",
            "unit_of_measurement": "beers",
            "state_class": "measurement",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_power",
                    "affected_entities": {("sensor.grid_power", "beers")},
                    "translation_placeholders": {
                        "power_units": ", ".join(tuple(UnitOfPower))
                    },
                }
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_grid_power_wrong_state_class(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating grid with power sensor having wrong state class."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [],
                    "flow_to": [],
                    "power": [
                        {
                            "stat_power": "sensor.grid_power",
                        }
                    ],
                    "cost_adjustment_day": 0.0,
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.grid_power",
        "1.5",
        {
            "device_class": "power",
            "unit_of_measurement": UnitOfPower.KILO_WATT,
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_state_class",
                    "affected_entities": {("sensor.grid_power", "total_increasing")},
                    "translation_placeholders": None,
                }
            ]
        ],
        "device_consumption": [],
    }
