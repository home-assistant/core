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
        "errors": [],
        "warnings": [],
        "energy_sources": [],
        "device_consumption": [],
    }


async def test_validation_device_consumption_entity_missing(hass, mock_energy_manager):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.not_exist"}]}
    )
    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [],
        "device_consumption": [
            {
                "errors": [],
                "warnings": [
                    {
                        "message": "Entity sensor.not_exist is not currently defined",
                        "link": None,
                    }
                ],
            }
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
        "errors": [],
        "warnings": [],
        "energy_sources": [],
        "device_consumption": [
            {
                "errors": [],
                "warnings": [
                    {
                        "message": "Entity sensor.unavailable is currently unavailable (unavailable)",
                        "link": None,
                    }
                ],
            }
        ],
    }


async def test_validation_device_consumption_entity_non_numeric(
    hass, mock_energy_manager
):
    """Test validating missing stat for device."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.non_numeric"}]}
    )
    hass.states.async_set("sensor.non_numeric", "123,123.10", {})

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [],
        "device_consumption": [
            {
                "errors": [
                    {
                        "message": "Entity sensor.non_numeric has non-numeric value 123,123.10",
                        "link": None,
                    }
                ],
                "warnings": [
                    {
                        "message": "Entity sensor.non_numeric has no unit of measurement",
                        "link": None,
                    }
                ],
            }
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
        "sensor.unexpected_unit", "10.10", {"unit_of_measurement": "beers"}
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [],
        "device_consumption": [
            {
                "errors": [
                    {
                        "message": "Entity sensor.unexpected_unit has an unexpected unit. Expected kWh or Wh",
                        "link": None,
                    }
                ],
                "warnings": [],
            }
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
        "errors": [],
        "warnings": [],
        "energy_sources": [],
        "device_consumption": [
            {
                "errors": [
                    {
                        "message": "Entity sensor.not_recorded needs to be tracked by the recorder",
                        "link": "https://www.home-assistant.io/integrations/recorder#configure-filter",
                    }
                ],
                "warnings": [],
            }
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
        "sensor.solar_production", "10.10", {"unit_of_measurement": "beers"}
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [
            {
                "errors": [
                    {
                        "message": "Entity sensor.solar_production has an unexpected unit. Expected kWh or Wh",
                        "link": None,
                    }
                ],
                "warnings": [],
            }
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
        "sensor.battery_import", "10.10", {"unit_of_measurement": "beers"}
    )
    hass.states.async_set(
        "sensor.battery_export", "10.10", {"unit_of_measurement": "beers"}
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [
            {
                "errors": [
                    {
                        "message": "Entity sensor.battery_import has an unexpected unit. Expected kWh or Wh",
                        "link": None,
                    },
                    {
                        "message": "Entity sensor.battery_export has an unexpected unit. Expected kWh or Wh",
                        "link": None,
                    },
                ],
                "warnings": [],
            }
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
        "sensor.grid_consumption_1", "10.10", {"unit_of_measurement": "beers"}
    )
    hass.states.async_set(
        "sensor.grid_production_1", "10.10", {"unit_of_measurement": "beers"}
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [
            {
                "errors": [
                    {
                        "message": "Entity sensor.grid_consumption_1 has an unexpected unit. Expected kWh or Wh",
                        "link": None,
                    },
                    {
                        "message": "Entity sensor.grid_cost_1 needs to be tracked by the recorder",
                        "link": "https://www.home-assistant.io/integrations/recorder#configure-filter",
                    },
                    {
                        "message": "Entity sensor.grid_production_1 has an unexpected unit. Expected kWh or Wh",
                        "link": None,
                    },
                    {
                        "message": "Entity sensor.grid_compensation_1 needs to be tracked by the recorder",
                        "link": "https://www.home-assistant.io/integrations/recorder#configure-filter",
                    },
                ],
                "warnings": [],
            }
        ],
        "device_consumption": [],
    }


async def test_validation_grid_price_not_exist(hass, mock_energy_manager):
    """Test validating grid with price entity that does not exist."""
    hass.states.async_set(
        "sensor.grid_consumption_1", "10.10", {"unit_of_measurement": "kWh"}
    )
    hass.states.async_set(
        "sensor.grid_production_1", "10.10", {"unit_of_measurement": "kWh"}
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
                        }
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_production_1",
                            "entity_energy_to": "sensor.grid_production_1",
                            "number_energy_price": 0.10,
                        }
                    ],
                }
            ]
        }
    )
    await hass.async_block_till_done()

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [
            {
                "errors": [
                    {
                        "message": "Unable to find entity sensor.grid_price_1",
                        "link": None,
                    },
                ],
                "warnings": [],
            }
        ],
        "device_consumption": [],
    }


@pytest.mark.parametrize(
    "state, unit, expected",
    (
        (
            "123,123.12",
            "$/kWh",
            "Entity sensor.grid_price_1 has non-numeric value 123,123.12",
        ),
        ("-100", "$/kWh", "Entity sensor.grid_price_1 has negative value -100.0"),
        (
            "123",
            "$/Ws",
            "Entity sensor.grid_price_1 has a unit that is not per kilowatt or watt hour",
        ),
    ),
)
async def test_validation_grid_price_errors(
    hass, mock_energy_manager, state, unit, expected
):
    """Test validating grid with price data that gives errors."""
    hass.states.async_set(
        "sensor.grid_consumption_1", "10.10", {"unit_of_measurement": "kWh"}
    )
    hass.states.async_set("sensor.grid_price_1", state, {"unit_of_measurement": unit})
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
                        }
                    ],
                    "flow_to": [],
                }
            ]
        }
    )
    await hass.async_block_till_done()

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [
            {
                "errors": [
                    {
                        "message": expected,
                        "link": None,
                    },
                ],
                "warnings": [],
            }
        ],
        "device_consumption": [],
    }


@pytest.mark.parametrize(
    "state, unit, expected",
    (("123", None, "Entity sensor.grid_price_1 has no unit of measurement"),),
)
async def test_validation_grid_price_warnings(
    hass, mock_energy_manager, state, unit, expected
):
    """Test validating grid with config that causes price warnings."""
    hass.states.async_set(
        "sensor.grid_consumption_1", "10.10", {"unit_of_measurement": "kWh"}
    )
    hass.states.async_set("sensor.grid_price_1", state, {"unit_of_measurement": unit})
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
                        }
                    ],
                    "flow_to": [],
                }
            ]
        }
    )
    await hass.async_block_till_done()

    assert (await validate.async_validate(hass)).as_dict() == {
        "errors": [],
        "warnings": [],
        "energy_sources": [
            {
                "errors": [],
                "warnings": [
                    {
                        "message": expected,
                        "link": None,
                    },
                ],
            }
        ],
        "device_consumption": [],
    }
