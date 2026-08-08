"""Test the Tesla Fleet services."""

from math import inf
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.services import (
    SERVICE_TIME_OF_USE,
    _tesla_day_ranges,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_platform
from .const import COMMAND_ERROR, RESPONSE_OK

from tests.common import MockConfigEntry

ENERGY_SITE_ENTITY = "sensor.energy_site_grid_power"

TIME_OF_USE_DATA = {
    "name": "Agile",
    "utility": "Octopus Energy",
    "currency": "gbp",
    "daily_charge": 0.6,
    "seasons": [
        {
            "name": "All year",
            "periods": [
                {
                    "name": "Agile low",
                    "days": ["monday", "wednesday", "friday"],
                    "start_time": "00:30:00",
                    "end_time": "04:30:00",
                    "buy_rate": -0.05,
                    "sell_rate": 0.15,
                }
            ],
        }
    ],
}

AGILE_LOW_PERIODS = [
    {
        "fromDayOfWeek": day,
        "toDayOfWeek": day,
        "fromHour": 0,
        "fromMinute": 30,
        "toHour": 4,
        "toMinute": 30,
    }
    for day in (0, 2, 4)
]

# Tesla's published tariffs always carry these, zeroed when unused.
UNUSED_CHARGES = {
    "monthly_minimum_bill": 0,
    "min_applicable_demand": 0,
    "max_applicable_demand": 0,
    "monthly_charges": 0,
    "daily_demand_charges": {},
}

EXPECTED_TARIFF = {
    "version": 1,
    "code": "home_assistant",
    "name": "Agile",
    "utility": "Octopus Energy",
    "currency": "GBP",
    "daily_charges": [{"name": "Charge", "amount": 0.6}],
    "demand_charges": {"ALL": {"rates": {"ALL": 0}}},
    "energy_charges": {"ALL": {"rates": {"AGILE_LOW": -0.05}}},
    "seasons": {"ALL": {"tou_periods": {"AGILE_LOW": {"periods": AGILE_LOW_PERIODS}}}},
    "sell_tariff": {
        "version": 1,
        "code": "",
        "currency": "",
        "name": "Agile",
        "utility": "Octopus Energy",
        "daily_charges": [{"name": "Charge", "amount": 0}],
        "demand_charges": {"ALL": {"rates": {"ALL": 0}}},
        "energy_charges": {"ALL": {"rates": {"AGILE_LOW": 0.15}}},
        "seasons": {
            "ALL": {"tou_periods": {"AGILE_LOW": {"periods": AGILE_LOW_PERIODS}}}
        },
        **UNUSED_CHARGES,
    },
    **UNUSED_CHARGES,
}


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        pytest.param(None, [(0, 6)], id="unset"),
        pytest.param(["sunday"], [(6, 6)], id="single_day"),
        pytest.param(["saturday", "sunday"], [(5, 6)], id="weekend"),
        pytest.param(["sunday", "monday"], [(6, 0)], id="sunday_monday"),
        pytest.param(
            ["monday", "wednesday", "friday"], [(0, 0), (2, 2), (4, 4)], id="disjoint"
        ),
        pytest.param(
            ["friday", "saturday", "sunday", "monday"], [(4, 0)], id="friday_to_monday"
        ),
        pytest.param(
            ["monday", "wednesday", "sunday"],
            [(6, 0), (2, 2)],
            id="wrap_preserves_middle",
        ),
        pytest.param(
            [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ],
            [(0, 6)],
            id="every_day",
        ),
    ],
)
def test_tesla_day_ranges(
    days: list[str] | None, expected: list[tuple[int, int]]
) -> None:
    """Test weekday selections convert into circular contiguous Tesla ranges."""
    assert _tesla_day_ranges(days) == expected


async def test_time_of_use_split_period(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test one label reused at two times of day, as Tesla's own tariffs do."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    with patch(
        "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
        return_value=RESPONSE_OK,
    ) as set_time_of_use:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                "name": "Split",
                "utility": "Octopus Energy",
                "currency": "GBP",
                "seasons": [
                    {
                        "name": "All year",
                        "periods": [
                            {
                                "name": "Off peak",
                                "start_time": "00:00:00",
                                "end_time": "07:00:00",
                                "buy_rate": 0.09,
                            },
                            {
                                "name": "Off peak",
                                "start_time": "22:00:00",
                                "end_time": "00:00:00",
                                "buy_rate": 0.09,
                            },
                        ],
                    }
                ],
            },
            blocking=True,
        )

    tariff = set_time_of_use.call_args[0][0]
    assert tariff["energy_charges"]["ALL"]["rates"] == {"OFF_PEAK": 0.09}
    assert tariff["seasons"]["ALL"]["tou_periods"]["OFF_PEAK"]["periods"] == [
        {
            "fromDayOfWeek": 0,
            "toDayOfWeek": 6,
            "fromHour": 0,
            "fromMinute": 0,
            "toHour": 7,
            "toMinute": 0,
        },
        {
            "fromDayOfWeek": 0,
            "toDayOfWeek": 6,
            "fromHour": 22,
            "fromMinute": 0,
            "toHour": 0,
            "toMinute": 0,
        },
    ]


async def test_time_of_use(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the time_of_use service builds the expected Tesla tariff."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    assert hass.services.has_service(DOMAIN, SERVICE_TIME_OF_USE)

    with patch(
        "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
        return_value=RESPONSE_OK,
    ) as set_time_of_use:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {CONF_DEVICE_ID: energy_device, **TIME_OF_USE_DATA},
            blocking=True,
        )
        set_time_of_use.assert_called_once_with(EXPECTED_TARIFF)


async def test_time_of_use_seasons(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a dated multi-season tariff without export rates."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    with patch(
        "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
        return_value=RESPONSE_OK,
    ) as set_time_of_use:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                "name": "Seasonal",
                "utility": "Octopus Energy",
                "currency": "GBP",
                "seasons": [
                    {
                        "name": "Summer",
                        "start_month": 4,
                        "start_day": 1,
                        "end_month": 9,
                        "end_day": 30,
                        "periods": [{"name": "On peak", "buy_rate": 0.3}],
                    },
                    {
                        "name": "Winter",
                        "start_month": 10,
                        "start_day": 1,
                        "end_month": 3,
                        "end_day": 31,
                        "periods": [{"name": "On peak", "buy_rate": 0.4}],
                    },
                ],
            },
            blocking=True,
        )

    tariff = set_time_of_use.call_args[0][0]
    all_week = [
        {
            "fromDayOfWeek": 0,
            "toDayOfWeek": 6,
            "fromHour": 0,
            "fromMinute": 0,
            "toHour": 0,
            "toMinute": 0,
        }
    ]
    assert tariff["daily_charges"] == [{"name": "Charge", "amount": 0}]
    assert "sell_tariff" not in tariff
    assert tariff["energy_charges"] == {
        "Summer": {"rates": {"ON_PEAK": 0.3}},
        "Winter": {"rates": {"ON_PEAK": 0.4}},
        "ALL": {"rates": {"ALL": 0}},
    }
    assert tariff["demand_charges"] == {
        "ALL": {"rates": {"ALL": 0}},
        "Summer": {"rates": {}},
        "Winter": {"rates": {}},
    }
    assert tariff["seasons"]["Summer"] == {
        "tou_periods": {"ON_PEAK": {"periods": all_week}},
        "fromMonth": 4,
        "fromDay": 1,
        "toMonth": 9,
        "toDay": 30,
    }


async def test_time_of_use_wrapping_days(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a weekend-wrapping day selection becomes a single Tesla range."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    with patch(
        "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
        return_value=RESPONSE_OK,
    ) as set_time_of_use:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {
                CONF_DEVICE_ID: energy_device,
                "name": "Weekend",
                "utility": "Octopus Energy",
                "currency": "GBP",
                "seasons": [
                    {
                        "name": "All year",
                        "periods": [
                            {
                                "name": "Off peak",
                                "days": [
                                    "friday",
                                    "saturday",
                                    "sunday",
                                    "monday",
                                ],
                                "buy_rate": 0.1,
                            }
                        ],
                    }
                ],
            },
            blocking=True,
        )

    periods = set_time_of_use.call_args[0][0]["seasons"]["ALL"]["tou_periods"]
    assert periods["OFF_PEAK"]["periods"] == [
        {
            "fromDayOfWeek": 4,
            "toDayOfWeek": 0,
            "fromHour": 0,
            "fromMinute": 0,
            "toHour": 0,
            "toMinute": 0,
        }
    ]


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"seasons": [{"name": "All year", "periods": []}]},
            id="no_periods",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "All year",
                        "periods": [
                            {
                                "name": "Peak",
                                "start_time": "01:00:00",
                                "buy_rate": 0.1,
                            }
                        ],
                    }
                ]
            },
            id="only_start_time",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "Summer",
                        "start_month": 4,
                        "periods": [{"name": "Peak", "buy_rate": 0.1}],
                    },
                    {
                        "name": "Winter",
                        "start_month": 10,
                        "start_day": 1,
                        "end_month": 3,
                        "end_day": 31,
                        "periods": [{"name": "Peak", "buy_rate": 0.2}],
                    },
                ]
            },
            id="partial_season_dates",
        ),
        pytest.param(
            {
                "seasons": [
                    {"name": "One", "periods": [{"name": "Peak", "buy_rate": 0.1}]},
                    {"name": "Two", "periods": [{"name": "Peak", "buy_rate": 0.2}]},
                ]
            },
            id="multiple_undated_seasons",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "All year",
                        "periods": [
                            {"name": "Peak", "buy_rate": 0.3, "sell_rate": 0.1},
                            {"name": "Off peak", "buy_rate": 0.1},
                        ],
                    }
                ]
            },
            id="partial_export_rates",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "All year",
                        "periods": [
                            {"name": "On peak", "buy_rate": 0.3},
                            {"name": "On  Peak", "buy_rate": 0.1},
                        ],
                    }
                ]
            },
            id="colliding_period_labels",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "All year",
                        "periods": [{"name": "Peak", "buy_rate": inf}],
                    }
                ]
            },
            id="non_finite_rate",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "ALL",
                        "start_month": 1,
                        "start_day": 1,
                        "end_month": 6,
                        "end_day": 30,
                        "periods": [{"name": "Peak", "buy_rate": 0.3}],
                    },
                    {
                        "name": "Winter",
                        "start_month": 7,
                        "start_day": 1,
                        "end_month": 12,
                        "end_day": 31,
                        "periods": [{"name": "Peak", "buy_rate": 0.4}],
                    },
                ]
            },
            id="reserved_season_name",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "All year",
                        "periods": [
                            {"name": "Peak", "days": ["monday"], "buy_rate": 0.2},
                            {"name": "Peak", "days": ["tuesday"], "buy_rate": 0.4},
                        ],
                    }
                ]
            },
            id="repeated_period_conflicting_rates",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "Summer",
                        "start_month": 4,
                        "start_day": 1,
                        "end_month": 9,
                        "end_day": 30,
                        "periods": [
                            {"name": "Peak", "buy_rate": 0.3, "sell_rate": 0.1}
                        ],
                    },
                    {
                        "name": "Winter",
                        "start_month": 10,
                        "start_day": 1,
                        "end_month": 3,
                        "end_day": 31,
                        "periods": [{"name": "Peak", "buy_rate": 0.4}],
                    },
                ]
            },
            id="partial_export_across_seasons",
        ),
        pytest.param(
            {
                "seasons": [
                    {
                        "name": "Summer",
                        "start_month": 2,
                        "start_day": 30,
                        "end_month": 9,
                        "end_day": 30,
                        "periods": [{"name": "Peak", "buy_rate": 0.3}],
                    },
                    {
                        "name": "Winter",
                        "start_month": 10,
                        "start_day": 1,
                        "end_month": 1,
                        "end_day": 31,
                        "periods": [{"name": "Peak", "buy_rate": 0.4}],
                    },
                ]
            },
            id="impossible_calendar_date",
        ),
        pytest.param({"currency": "pounds"}, id="invalid_currency"),
        pytest.param({"daily_charge": -1}, id="negative_daily_charge"),
    ],
)
async def test_time_of_use_invalid_payload(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    payload: dict[str, Any],
) -> None:
    """Test that malformed tariff input is rejected before any command is sent."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    with (
        patch(
            "tesla_fleet_api.tesla.EnergySite.time_of_use_settings"
        ) as set_time_of_use,
        pytest.raises(vol.Invalid),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {CONF_DEVICE_ID: energy_device, **TIME_OF_USE_DATA, **payload},
            blocking=True,
        )
    set_time_of_use.assert_not_called()


async def test_time_of_use_command_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a Tesla error response raises HomeAssistantError."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    with (
        patch(
            "tesla_fleet_api.tesla.EnergySite.time_of_use_settings",
            return_value=COMMAND_ERROR,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {CONF_DEVICE_ID: energy_device, **TIME_OF_USE_DATA},
            blocking=True,
        )


async def test_time_of_use_invalid_device(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test that an unknown device_id raises ServiceValidationError."""
    await setup_platform(hass, normal_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {CONF_DEVICE_ID: "not-a-real-device", **TIME_OF_USE_DATA},
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_device"


async def test_time_of_use_entry_not_loaded(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test calling the service after the config entry is unloaded."""
    await setup_platform(hass, normal_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    assert await hass.config_entries.async_unload(normal_config_entry.entry_id)
    await hass.async_block_till_done()
    assert normal_config_entry.state is ConfigEntryState.NOT_LOADED

    # Service stays registered at domain level, but the entry is gone.
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {CONF_DEVICE_ID: energy_device, **TIME_OF_USE_DATA},
            blocking=True,
        )
    assert exc_info.value.translation_key == "entry_not_loaded"


async def test_time_of_use_missing_scope(
    hass: HomeAssistant,
    readonly_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the service rejects an entry without the energy commands scope."""
    await setup_platform(hass, readonly_config_entry)

    energy_device = entity_registry.async_get(ENERGY_SITE_ENTITY).device_id

    with (
        patch(
            "tesla_fleet_api.tesla.EnergySite.time_of_use_settings"
        ) as set_time_of_use,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TIME_OF_USE,
            {CONF_DEVICE_ID: energy_device, **TIME_OF_USE_DATA},
            blocking=True,
        )
    assert exc_info.value.translation_key == "missing_scope_energy_cmds"
    set_time_of_use.assert_not_called()
