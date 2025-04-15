"""Test that validation works."""

from unittest.mock import patch

import pytest

from homeassistant.components.energy import async_get_manager, validate
from homeassistant.components.energy.data import EnergyManager
from homeassistant.components.recorder import Recorder
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSON_DUMP
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_is_entity_recorded():
    """Mock recorder.is_entity_recorded."""
    mocks = {}

    with patch(
        "homeassistant.components.recorder.is_entity_recorded",
        side_effect=lambda hass, entity_id: mocks.get(entity_id, True),
    ):
        yield mocks


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


async def test_validation_empty_config(hass: HomeAssistant) -> None:
    """Test validating an empty config."""
    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [],
    }


@pytest.mark.parametrize(
    ("state_class", "energy_unit", "extra"),
    [
        ("total_increasing", UnitOfEnergy.KILO_WATT_HOUR, {}),
        ("total_increasing", UnitOfEnergy.MEGA_WATT_HOUR, {}),
        ("total_increasing", UnitOfEnergy.WATT_HOUR, {}),
        ("total", UnitOfEnergy.KILO_WATT_HOUR, {}),
        ("total", UnitOfEnergy.KILO_WATT_HOUR, {"last_reset": "abc"}),
        ("measurement", UnitOfEnergy.KILO_WATT_HOUR, {"last_reset": "abc"}),
        ("total_increasing", UnitOfEnergy.GIGA_JOULE, {}),
    ],
)
async def test_validation(
    hass: HomeAssistant,
    mock_energy_manager,
    mock_get_metadata,
    state_class,
    energy_unit,
    extra,
) -> None:
    """Test validating success."""
    for key in ("device_cons", "battery_import", "battery_export", "solar_production"):
        hass.states.async_set(
            f"sensor.{key}",
            "123",
            {
                "device_class": "energy",
                "unit_of_measurement": energy_unit,
                "state_class": state_class,
                **extra,
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


async def test_validation_device_consumption_entity_missing(
    hass: HomeAssistant, mock_energy_manager
) -> None:
    """Test validating missing entity for device."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.not_exist"}]}
    )
    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "statistics_not_defined",
                    "affected_entities": {("sensor.not_exist", None)},
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": {("sensor.not_exist", None)},
                    "translation_placeholders": None,
                },
            ]
        ],
    }


async def test_validation_device_consumption_stat_missing(
    hass: HomeAssistant, mock_energy_manager
) -> None:
    """Test validating missing statistic for device with non entity stats."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "external:not_exist"}]}
    )
    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "statistics_not_defined",
                    "affected_entities": {("external:not_exist", None)},
                    "translation_placeholders": None,
                }
            ]
        ],
    }


async def test_validation_device_consumption_entity_unavailable(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
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
                    "affected_entities": {("sensor.unavailable", "unavailable")},
                    "translation_placeholders": None,
                }
            ]
        ],
    }


async def test_validation_device_consumption_entity_non_numeric(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
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
                    "affected_entities": {("sensor.non_numeric", "123,123.10")},
                    "translation_placeholders": None,
                },
            ]
        ],
    }


async def test_validation_device_consumption_entity_unexpected_unit(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
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
                    "affected_entities": {("sensor.unexpected_unit", "beers")},
                    "translation_placeholders": {
                        "energy_units": "GJ, kWh, MJ, MWh, Wh"
                    },
                }
            ]
        ],
    }


async def test_validation_device_consumption_recorder_not_tracked(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
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
                    "affected_entities": {("sensor.not_recorded", None)},
                    "translation_placeholders": None,
                }
            ]
        ],
    }


async def test_validation_device_consumption_no_last_reset(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
    """Test validating device based on untracked entity."""
    await mock_energy_manager.async_update(
        {"device_consumption": [{"stat_consumption": "sensor.no_last_reset"}]}
    )
    hass.states.async_set(
        "sensor.no_last_reset",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "kWh",
            "state_class": "measurement",
        },
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [],
        "device_consumption": [
            [
                {
                    "type": "entity_state_class_measurement_no_last_reset",
                    "affected_entities": {("sensor.no_last_reset", None)},
                    "translation_placeholders": None,
                }
            ]
        ],
    }


async def test_validation_solar(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
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
                    "affected_entities": {("sensor.solar_production", "beers")},
                    "translation_placeholders": {
                        "energy_units": "GJ, kWh, MJ, MWh, Wh"
                    },
                }
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_battery(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata
) -> None:
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
                    "affected_entities": {
                        ("sensor.battery_import", "beers"),
                        ("sensor.battery_export", "beers"),
                    },
                    "translation_placeholders": {
                        "energy_units": "GJ, kWh, MJ, MWh, Wh"
                    },
                },
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_grid(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating grid with sensors for energy and cost/compensation."""
    mock_is_entity_recorded["sensor.grid_cost_1"] = False
    mock_is_entity_recorded["sensor.grid_compensation_1"] = False
    mock_get_metadata["sensor.grid_cost_1"] = None
    mock_get_metadata["sensor.grid_compensation_1"] = None
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

    result = await validate.async_validate(hass)
    # verify its also json serializable
    JSON_DUMP(result)

    assert result.as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_energy",
                    "affected_entities": {
                        ("sensor.grid_consumption_1", "beers"),
                        ("sensor.grid_production_1", "beers"),
                    },
                    "translation_placeholders": {
                        "energy_units": "GJ, kWh, MJ, MWh, Wh"
                    },
                },
                {
                    "type": "statistics_not_defined",
                    "affected_entities": {
                        ("sensor.grid_cost_1", None),
                        ("sensor.grid_compensation_1", None),
                    },
                    "translation_placeholders": None,
                },
                {
                    "type": "recorder_untracked",
                    "affected_entities": {
                        ("sensor.grid_cost_1", None),
                        ("sensor.grid_compensation_1", None),
                    },
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": {
                        ("sensor.grid_cost_1", None),
                        ("sensor.grid_compensation_1", None),
                    },
                    "translation_placeholders": None,
                },
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_grid_external_cost_compensation(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating grid with non entity stats for energy and cost/compensation."""
    mock_get_metadata["external:grid_cost_1"] = None
    mock_get_metadata["external:grid_compensation_1"] = None
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.grid_consumption_1",
                            "stat_cost": "external:grid_cost_1",
                        }
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_production_1",
                            "stat_compensation": "external:grid_compensation_1",
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
                    "affected_entities": {
                        ("sensor.grid_consumption_1", "beers"),
                        ("sensor.grid_production_1", "beers"),
                    },
                    "translation_placeholders": {
                        "energy_units": "GJ, kWh, MJ, MWh, Wh"
                    },
                },
                {
                    "type": "statistics_not_defined",
                    "affected_entities": {
                        ("external:grid_cost_1", None),
                        ("external:grid_compensation_1", None),
                    },
                    "translation_placeholders": None,
                },
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_grid_price_not_exist(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata, mock_is_entity_recorded
) -> None:
    """Test validating grid with errors.

    - The price entity for the auto generated cost entity does not exist.
    - The auto generated cost entities are not recorded.
    """
    mock_is_entity_recorded["sensor.grid_consumption_1_cost"] = False
    mock_is_entity_recorded["sensor.grid_production_1_compensation"] = False
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
                            "entity_energy_price": "sensor.grid_price_1",
                            "number_energy_price": None,
                        }
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_production_1",
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
                    "affected_entities": {("sensor.grid_price_1", None)},
                    "translation_placeholders": None,
                },
                {
                    "type": "recorder_untracked",
                    "affected_entities": {
                        ("sensor.grid_consumption_1_cost", None),
                        ("sensor.grid_production_1_compensation", None),
                    },
                    "translation_placeholders": None,
                },
            ]
        ],
        "device_consumption": [],
    }


async def test_validation_grid_auto_cost_entity_errors(
    hass: HomeAssistant,
    mock_energy_manager,
    mock_get_metadata,
    mock_is_entity_recorded,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validating grid when the auto generated cost entity config is incorrect.

    The intention of the test is to make sure the validation does not throw due to the
    bad config.
    """
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
                            "entity_energy_price": None,
                            "number_energy_price": 0.20,
                        }
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_production_1",
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
        "energy_sources": [[]],
        "device_consumption": [],
    }


@pytest.mark.parametrize(
    ("state", "unit", "expected"),
    [
        (
            "123,123.12",
            "$/kWh",
            {
                "type": "entity_state_non_numeric",
                "affected_entities": {("sensor.grid_price_1", "123,123.12")},
                "translation_placeholders": None,
            },
        ),
        (
            "123",
            "$/Ws",
            {
                "type": "entity_unexpected_unit_energy_price",
                "affected_entities": {("sensor.grid_price_1", "$/Ws")},
                "translation_placeholders": {
                    "price_units": "EUR/GJ, EUR/kWh, EUR/MJ, EUR/MWh, EUR/Wh"
                },
            },
        ),
    ],
)
async def test_validation_grid_price_errors(
    hass: HomeAssistant, mock_energy_manager, mock_get_metadata, state, unit, expected
) -> None:
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


async def test_validation_gas(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
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
                    "entity_energy_price": "sensor.gas_price_1",
                },
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_3",
                    "entity_energy_price": "sensor.gas_price_2",
                },
            ]
        }
    )
    await hass.async_block_till_done()
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
    hass.states.async_set(
        "sensor.gas_price_1",
        "10.10",
        {"unit_of_measurement": "EUR/m³", "state_class": "total_increasing"},
    )
    hass.states.async_set(
        "sensor.gas_price_2",
        "10.10",
        {"unit_of_measurement": "EUR/invalid", "state_class": "total_increasing"},
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_gas",
                    "affected_entities": {("sensor.gas_consumption_1", "beers")},
                    "translation_placeholders": {
                        "energy_units": "GJ, kWh, MJ, MWh, Wh",
                        "gas_units": "CCF, ft³, m³",
                    },
                },
                {
                    "type": "recorder_untracked",
                    "affected_entities": {("sensor.gas_cost_1", None)},
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": {("sensor.gas_cost_1", None)},
                    "translation_placeholders": None,
                },
            ],
            [],
            [],
            [
                {
                    "type": "entity_unexpected_device_class",
                    "affected_entities": {("sensor.gas_consumption_4", None)},
                    "translation_placeholders": None,
                },
            ],
            [
                {
                    "type": "entity_unexpected_unit_gas_price",
                    "affected_entities": {("sensor.gas_price_2", "EUR/invalid")},
                    "translation_placeholders": {
                        "price_units": (
                            "EUR/GJ, EUR/kWh, EUR/MJ, EUR/MWh, EUR/Wh, EUR/CCF, EUR/ft³, EUR/m³"
                        )
                    },
                },
            ],
        ],
        "device_consumption": [],
    }


async def test_validation_gas_no_costs_tracking(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating gas with sensors without cost tracking."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "gas",
                    "stat_energy_from": "sensor.gas_consumption_1",
                    "stat_cost": None,
                    "entity_energy_price": None,
                    "number_energy_price": None,
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

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
    }


async def test_validation_grid_no_costs_tracking(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating grid with sensors for energy without cost tracking."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.grid_energy",
                            "stat_cost": None,
                            "entity_energy_price": None,
                            "number_energy_price": None,
                        },
                    ],
                    "flow_to": [
                        {
                            "stat_energy_to": "sensor.grid_energy",
                            "stat_cost": None,
                            "entity_energy_price": None,
                            "number_energy_price": None,
                        },
                    ],
                    "cost_adjustment_day": 0.0,
                }
            ]
        }
    )
    hass.states.async_set(
        "sensor.grid_energy",
        "10.10",
        {
            "device_class": "energy",
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
        },
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
    }


async def test_validation_water(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating water with sensors for energy and cost/compensation."""
    mock_is_entity_recorded["sensor.water_cost_1"] = False
    mock_is_entity_recorded["sensor.water_compensation_1"] = False
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption_1",
                    "stat_cost": "sensor.water_cost_1",
                },
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption_2",
                    "stat_cost": "sensor.water_cost_2",
                },
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption_3",
                    "stat_cost": "sensor.water_cost_2",
                },
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption_4",
                    "entity_energy_price": "sensor.water_price_1",
                },
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption_3",
                    "entity_energy_price": "sensor.water_price_2",
                },
            ]
        }
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "sensor.water_consumption_1",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "beers",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.water_consumption_2",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "ft³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.water_consumption_3",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )
    hass.states.async_set(
        "sensor.water_consumption_4",
        "10.10",
        {"unit_of_measurement": "beers", "state_class": "total_increasing"},
    )
    hass.states.async_set(
        "sensor.water_cost_2",
        "10.10",
        {"unit_of_measurement": "EUR/kWh", "state_class": "total_increasing"},
    )
    hass.states.async_set(
        "sensor.water_price_1",
        "10.10",
        {"unit_of_measurement": "EUR/m³", "state_class": "total_increasing"},
    )
    hass.states.async_set(
        "sensor.water_price_2",
        "10.10",
        {"unit_of_measurement": "EUR/invalid", "state_class": "total_increasing"},
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [
            [
                {
                    "type": "entity_unexpected_unit_water",
                    "affected_entities": {("sensor.water_consumption_1", "beers")},
                    "translation_placeholders": {"water_units": "CCF, ft³, m³, gal, L"},
                },
                {
                    "type": "recorder_untracked",
                    "affected_entities": {("sensor.water_cost_1", None)},
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": {("sensor.water_cost_1", None)},
                    "translation_placeholders": None,
                },
            ],
            [],
            [],
            [
                {
                    "type": "entity_unexpected_device_class",
                    "affected_entities": {("sensor.water_consumption_4", None)},
                    "translation_placeholders": None,
                },
            ],
            [
                {
                    "type": "entity_unexpected_unit_water_price",
                    "affected_entities": {("sensor.water_price_2", "EUR/invalid")},
                    "translation_placeholders": {
                        "price_units": "EUR/CCF, EUR/ft³, EUR/m³, EUR/gal, EUR/L"
                    },
                },
            ],
        ],
        "device_consumption": [],
    }


async def test_validation_water_no_costs_tracking(
    hass: HomeAssistant, mock_energy_manager, mock_is_entity_recorded, mock_get_metadata
) -> None:
    """Test validating water with sensors without cost tracking."""
    await mock_energy_manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "water",
                    "stat_energy_from": "sensor.water_consumption_1",
                    "stat_cost": None,
                    "entity_energy_price": None,
                    "number_energy_price": None,
                },
            ]
        }
    )
    hass.states.async_set(
        "sensor.water_consumption_1",
        "10.10",
        {
            "device_class": "water",
            "unit_of_measurement": "m³",
            "state_class": "total_increasing",
        },
    )

    assert (await validate.async_validate(hass)).as_dict() == {
        "energy_sources": [[]],
        "device_consumption": [],
    }
