"""Test flow rate (stat_rate) validation for gas and water sources."""

import pytest

from homeassistant.components.energy import validate
from homeassistant.components.energy.data import EnergyManager
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant

FLOW_RATE_UNITS_STRING = ", ".join(tuple(UnitOfVolumeFlowRate))


@pytest.fixture(autouse=True)
async def setup_energy_for_validation(
    mock_energy_manager: EnergyManager,
) -> EnergyManager:
    """Ensure energy manager is set up for validation tests."""
    return mock_energy_manager


async def test_validation_gas_flow_rate_valid(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating gas with valid flow rate sensor."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption",
                    "stat_rate": "sensor.gas_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_flow_rate",
        "1.5",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            "state_class": "measurement",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_gas_flow_rate_wrong_unit(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating gas with flow rate sensor having wrong unit."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption",
                    "stat_rate": "sensor.gas_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_flow_rate",
        "1.5",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": "beers",
            "state_class": "measurement",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_volume_flow_rate",
                    "affected_entities": {("sensor.gas_flow_rate", "beers")},
                    "translation_placeholders": {
                        "flow_rate_units": FLOW_RATE_UNITS_STRING
                    },
                }
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_gas_flow_rate_wrong_state_class(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating gas with flow rate sensor having wrong state class."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption",
                    "stat_rate": "sensor.gas_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_flow_rate",
        "1.5",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_state_class",
                    "affected_entities": {("sensor.gas_flow_rate", "total_increasing")},
                    "translation_placeholders": None,
                }
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_gas_flow_rate_entity_missing(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating gas with missing flow rate sensor."""
    mock_get_metadata["sensor.missing_flow_rate"] = None
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption",
                    "stat_rate": "sensor.missing_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "statistics_not_defined",
                    "affected_entities": {("sensor.missing_flow_rate", None)},
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": {("sensor.missing_flow_rate", None)},
                    "translation_placeholders": None,
                },
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_gas_without_flow_rate(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating gas without flow rate sensor still works."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_water_flow_rate_valid(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating water with valid flow rate sensor."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption",
                    "stat_rate": "sensor.water_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.water_consumption",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.water_flow_rate",
        "2.5",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            "state_class": "measurement",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_water_flow_rate_wrong_unit(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating water with flow rate sensor having wrong unit."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption",
                    "stat_rate": "sensor.water_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.water_consumption",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.water_flow_rate",
        "2.5",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": "beers",
            "state_class": "measurement",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_volume_flow_rate",
                    "affected_entities": {("sensor.water_flow_rate", "beers")},
                    "translation_placeholders": {
                        "flow_rate_units": FLOW_RATE_UNITS_STRING
                    },
                }
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_water_flow_rate_wrong_state_class(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating water with flow rate sensor having wrong state class."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption",
                    "stat_rate": "sensor.water_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.water_consumption",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.water_flow_rate",
        "2.5",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_state_class",
                    "affected_entities": {
                        ("sensor.water_flow_rate", "total_increasing")
                    },
                    "translation_placeholders": None,
                }
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_water_flow_rate_entity_missing(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating water with missing flow rate sensor."""
    mock_get_metadata["sensor.missing_flow_rate"] = None
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption",
                    "stat_rate": "sensor.missing_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.water_consumption",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "statistics_not_defined",
                    "affected_entities": {("sensor.missing_flow_rate", None)},
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": {("sensor.missing_flow_rate", None)},
                    "translation_placeholders": None,
                },
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_water_without_flow_rate(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating water without flow rate sensor still works."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.water_consumption",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_gas_flow_rate_different_units(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating gas with flow rate sensors using different valid units."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_1",
                    "stat_rate": "sensor.gas_flow_m3h",
                },
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_2",
                    "stat_rate": "sensor.gas_flow_lmin",
                },
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption_1",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_consumption_2",
        "20.20",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_flow_m3h",
        "1.5",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            "state_class": "measurement",
        },
    )
    hass.states.async_set(
        "sensor.gas_flow_lmin",
        "25.0",
        {
            "device_class": "volume_flow_rate",
            "unit_of_measurement": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            "state_class": "measurement",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [[], []],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_gas_flow_rate_recorder_untracked(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating gas with flow rate sensor not tracked by recorder."""
    mock_is_entity_recorded["sensor.untracked_flow_rate"] = False

    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption",
                    "stat_rate": "sensor.untracked_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "recorder_untracked",
                    "affected_entities": {("sensor.untracked_flow_rate", None)},
                    "translation_placeholders": None,
                }
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }


async def test_validation_water_flow_rate_recorder_untracked(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating water with flow rate sensor not tracked by recorder."""
    mock_is_entity_recorded["sensor.untracked_flow_rate"] = False

    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption",
                    "stat_rate": "sensor.untracked_flow_rate",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.water_consumption",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )

    result = await validate.async_validate(hass)
    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "recorder_untracked",
                    "affected_entities": {("sensor.untracked_flow_rate", None)},
                    "translation_placeholders": None,
                }
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [],
    }
