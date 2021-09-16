"""Test that validation works."""
from unittest.mock import patch

import pytest

from homeassistant.components.energy import async_get_manager, validate
from homeassistant.setup import async_setup_component

from tests.common import async_init_recorder_component


@pytest.fixture
def mock_is_entity_recorded():
    """Mock recorder.is_entity_recorded."""
    mocks = {}

    with patch(
        "homeassistant.components.recorder.is_entity_recorded",
        side_effect=lambda hass, entity_id: mocks.get(entity_id, True),
    ):
        yield mocks


@pytest.fixture(autouse=True)
async def mock_energy_manager(hass):
    """Set up energy."""
    await async_init_recorder_component(hass)
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()
    return manager


async def test_validation_empty_config(hass):
    """Test validating an empty config."""
    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [],
    }


async def test_validation(hass, mock_energy_manager):
    """Test validating success."""
    for key in ("device_cons", "battery_import", "battery_export", "solar_production"):
        hass.states.async_set(
            f"sensor.{key}",
            "123",
            {
                "device_class": "energy",
                "unit_of_measurement": "kWh",
                "state_class": "total_increasing",
            },
        )

    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_import",
                    "stat_energy_to": "sensor.battery_export",
                },
                {"type": "solar", "stat_energy_from": "sensor.solar_production"},
            ],
            "device_consumption": [{"stat_consumption": "sensor.device_cons"}],
        }
    )
    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [[], []],
        "device_consumption": [[]],
    }


async def test_validation_device_consumption_entity_missing(hass, mock_energy_manager):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.not_exist"}]}
    )
    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "entity_not_defined",
                    "identifier": "sensor.not_exist",
                    "value": None,
                }
            ]
        ],
    }


async def test_validation_device_consumption_entity_unavailable(
    hass, mock_energy_manager
):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.unavailable"}]}
    )
    hass.states.async_set("sensor.unavailable", "unavailable", {})

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "entity_unavailable",
                    "identifier": "sensor.unavailable",
                    "value": "unavailable",
                }
            ]
        ],
    }


async def test_validation_device_consumption_entity_non_numeric(
    hass, mock_energy_manager
):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.non_numeric"}]}
    )
    hass.states.async_set("sensor.non_numeric", "123,123.10")

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "entity_state_non_numeric",
                    "identifier": "sensor.non_numeric",
                    "value": "123,123.10",
                },
            ]
        ],
    }


async def test_validation_device_consumption_entity_unexpected_unit(
    hass, mock_energy_manager
):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.unexpected_unit"}]}
    )
    hass.states.async_set(
        "sensor.unexpected_unit",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "entity_unexpected_unit_energy",
                    "identifier": "sensor.unexpected_unit",
                    "value": "beers",
                }
            ]
        ],
    }


async def test_validation_device_consumption_recorder_not_tracked(
    hass, mock_energy_manager, mock_is_entity_recorded
):
    """Test validating device based on untracked entity."""
    mock_is_entity_recorded["sensor.not_recorded"] = False
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.not_recorded"}]}
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "recorder_untracked",
                    "identifier": "sensor.not_recorded",
                    "value": None,
                }
            ]
        ],
    }


async def test_validation_solar(hass, mock_energy_manager):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {"type": "solar", "stat_energy_from": "sensor.solar_production"}
            ]
        }
    )
    hass.states.async_set(
        "sensor.solar_production",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_energy",
                    "identifier": "sensor.solar_production",
                    "value": "beers",
                }
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_battery(hass, mock_energy_manager):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_import",
                    "stat_energy_to": "sensor.battery_export",
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.battery_import",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.battery_export",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_energy",
                    "identifier": "sensor.battery_import",
                    "value": "beers",
                },
                {
                    "type": "entity_unexpected_unit_energy",
                    "identifier": "sensor.battery_export",
                    "value": "beers",
                },
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_grid(hass, mock_energy_manager, mock_is_entity_recorded):
    """Test validating grid with sensors for energy and cost/compensation."""
    mock_is_entity_recorded["sensor.grid_cost_1"] = False
    mock_is_entity_recorded["sensor.grid_compensation_1"] = False
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.grid_consumption_1",
                            "stat_cost": "sensor.grid_cost_1",
                        }
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_production_1",
                            "stat_compensation": "sensor.grid_compensation_1",
                        }
                    ],
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.grid_consumption_1",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.grid_production_1",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_energy",
                    "identifier": "sensor.grid_consumption_1",
                    "value": "beers",
                },
                {
                    "type": "recorder_untracked",
                    "identifier": "sensor.grid_cost_1",
                    "value": None,
                },
                {
                    "type": "entity_unexpected_unit_energy",
                    "identifier": "sensor.grid_production_1",
                    "value": "beers",
                },
                {
                    "type": "recorder_untracked",
                    "identifier": "sensor.grid_compensation_1",
                    "value": None,
                },
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_grid_price_not_exist(hass, mock_energy_manager):
    """Test validating grid with price entity that does not exist."""
    hass.states.async_set(
        "sensor.grid_consumption_1",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.grid_production_1",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
        },
    )
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.grid_consumption_1",
                            "entity_energy_from": "sensor.grid_consumption_1",
                            "entity_energy_price": "sensor.grid_price_1",
                            "number_energy_price": None,
                        }
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_production_1",
                            "entity_energy_to": "sensor.grid_production_1",
                            "entity_energy_price": None,
                            "number_energy_price": 0.10,
                        }
                    ],
                }
            ]
        }
    )
    await hass.async_block_till_done()

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_not_defined",
                    "identifier": "sensor.grid_price_1",
                    "value": None,
                }
            ]
        ],
        "device_consumption": [],
    }


@pytest.mark.parametrize(
    "state, unit, expected",
    (
        (
            "123,123.12",
            "$/kWh",
            {
                "type": "entity_state_non_numeric",
                "identifier": "sensor.grid_price_1",
                "value": "123,123.12",
            },
        ),
        (
            "123",
            "$/Ws",
            {
                "type": "entity_unexpected_unit_price",
                "identifier": "sensor.grid_price_1",
                "value": "$/Ws",
            },
        ),
    ),
)
async def test_validation_grid_price_errors(
    hass, mock_energy_manager, state, unit, expected
):
    """Test validating grid with price data that gives errors."""
    hass.states.async_set(
        "sensor.grid_consumption_1",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.grid_price_1",
        state,
        {"unit_of_measurement": unit, "state_class": "measurement"},
    )
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.grid_consumption_1",
                            "entity_energy_from": "sensor.grid_consumption_1",
                            "entity_energy_price": "sensor.grid_price_1",
                            "number_energy_price": None,
                        }
                    ],
                    "flow_to": [],
                }
            ]
        }
    )
    await hass.async_block_till_done()

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [expected],
        ],
        "device_consumption": [],
    }


async def test_validation_gas(hass, mock_energy_manager, mock_is_entity_recorded):
    """Test validating gas with sensors for energy and cost/compensation."""
    mock_is_entity_recorded["sensor.gas_cost_1"] = False
    mock_is_entity_recorded["sensor.gas_compensation_1"] = False
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_1",
                    "stat_cost": "sensor.gas_cost_1",
                },
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_2",
                    "stat_cost": "sensor.gas_cost_2",
                },
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_3",
                    "stat_cost": "sensor.gas_cost_2",
                },
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_4",
                    "stat_cost": "sensor.gas_cost_2",
                },
            ]
        }
    )
    hass.states.async_set(
        "sensor.gas_consumption_1",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_consumption_2",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_consumption_3",
        "10.10",
        {
            "device_class": "gas",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.gas_consumption_4",
        "10.10",
        {"unit_of_measurement": "beers", "state_class": "total_increasing"},
    )
    hass.states.async_set(
        "sensor.gas_cost_2",
        "10.10",
        {"unit_of_measurement": "EUR/kWh", "state_class": "total_increasing"},
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_gas",
                    "identifier": "sensor.gas_consumption_1",
                    "value": "beers",
                },
                {
                    "type": "recorder_untracked",
                    "identifier": "sensor.gas_cost_1",
                    "value": None,
                },
            ],
            [],
            [],
            [
                {
                    "type": "entity_unexpected_device_class",
                    "identifier": "sensor.gas_consumption_4",
                    "value": None,
                },
            ],
        ],
        "device_consumption": [],
    }
