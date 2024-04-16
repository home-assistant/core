"""Test the Energy websocket API."""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.energy import data, is_configured
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, flush_store, mock_platform
from tests.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
)
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_integration(recorder_mock, hass):
    """Set up the integration."""
    assert await async_setup_component(hass, "energy", {})


@pytest.fixture
def mock_energy_platform(hass):
    """Mock an energy platform."""
    hass.config.components.add("some_domain")
    mock_platform(
        hass,
        "some_domain.energy",
        Mock(
            async_get_solar_forecast=AsyncMock(
                return_value={
                    "wh_hours": {
                        "2021-06-27T13:00:00+00:00": 12,
                        "2021-06-27T14:00:00+00:00": 8,
                    }
                }
            )
        ),
    )


async def test_get_preferences_no_data(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we get error if no preferences set."""
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "energy/get_prefs"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"] == {"code": "not_found", "message": "No prefs"}


async def test_get_preferences_default(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test we get preferences."""
    assert not await is_configured(hass)
    manager = await data.async_get_manager(hass)
    manager.data = data.EnergyManager.default_preferences()
    client = await hass_ws_client(hass)

    assert not await is_configured(hass)

    await client.send_json({"id": 5, "type": "energy/get_prefs"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == data.EnergyManager.default_preferences()


async def test_save_preferences(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    mock_energy_platform,
) -> None:
    """Test we can save preferences."""
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    # Test saving default prefs is also valid.
    default_prefs = data.EnergyManager.default_preferences()

    await client.send_json({"id": 5, "type": "energy/save_prefs", **default_prefs})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == default_prefs

    new_prefs = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {
                        "stat_energy_from": "sensor.heat_pump_meter",
                        "stat_cost": "heat_pump_kwh_cost",
                        "entity_energy_price": None,
                        "number_energy_price": None,
                    },
                    {
                        "stat_energy_from": "sensor.heat_pump_meter_2",
                        "stat_cost": None,
                        "entity_energy_price": None,
                        "number_energy_price": 0.20,
                    },
                ],
                "flow_to": [
                    {
                        "stat_energy_to": "sensor.return_to_grid_peak",
                        "stat_compensation": None,
                        "entity_energy_price": None,
                        "number_energy_price": None,
                    },
                    {
                        "stat_energy_to": "sensor.return_to_grid_offpeak",
                        "stat_compensation": None,
                        "entity_energy_price": None,
                        "number_energy_price": 0.20,
                    },
                ],
                "cost_adjustment_day": 1.2,
            },
            {
                "type": "solar",
                "stat_energy_from": "my_solar_production",
                "config_entry_solar_forecast": ["predicted_config_entry"],
            },
            {
                "type": "battery",
                "stat_energy_from": "my_battery_draining",
                "stat_energy_to": "my_battery_charging",
            },
        ],
        "device_consumption": [{"stat_consumption": "some_device_usage"}],
    }

    await client.send_json({"id": 6, "type": "energy/save_prefs", **new_prefs})

    msg = await client.receive_json()

    assert msg["id"] == 6
    assert msg["success"]
    assert msg["result"] == new_prefs

    assert data.STORAGE_KEY not in hass_storage, "expected not to be written yet"

    await flush_store((await data.async_get_manager(hass))._store)

    assert hass_storage[data.STORAGE_KEY]["data"] == new_prefs

    assert await is_configured(hass)

    # Verify info reflects data.
    await client.send_json({"id": 7, "type": "energy/info"})

    msg = await client.receive_json()

    assert msg["id"] == 7
    assert msg["success"]
    assert msg["result"] == {
        "cost_sensors": {
            "sensor.heat_pump_meter_2": "sensor.heat_pump_meter_2_cost",
            "sensor.return_to_grid_offpeak": (
                "sensor.return_to_grid_offpeak_compensation"
            ),
        },
        "solar_forecast_domains": ["some_domain"],
    }

    # Prefs with limited options
    new_prefs_2 = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {
                        "stat_energy_from": "sensor.heat_pump_meter",
                        "stat_cost": None,
                        "entity_energy_price": None,
                        "number_energy_price": None,
                    }
                ],
                "flow_to": [],
                "cost_adjustment_day": 1.2,
            },
            {
                "type": "solar",
                "stat_energy_from": "my_solar_production",
                "config_entry_solar_forecast": None,
            },
        ],
    }

    await client.send_json({"id": 8, "type": "energy/save_prefs", **new_prefs_2})

    msg = await client.receive_json()

    assert msg["id"] == 8
    assert msg["success"]
    assert msg["result"] == {**new_prefs, **new_prefs_2}


async def test_handle_duplicate_from_stat(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we handle duplicate from stats."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "energy/save_prefs",
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [
                        {
                            "stat_energy_from": "sensor.heat_pump_meter",
                            "stat_cost": None,
                            "entity_energy_price": None,
                            "number_energy_price": None,
                        },
                        {
                            "stat_energy_from": "sensor.heat_pump_meter",
                            "stat_cost": None,
                            "entity_energy_price": None,
                            "number_energy_price": None,
                        },
                    ],
                    "flow_to": [],
                    "cost_adjustment_day": 0,
                },
            ],
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


async def test_validate(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can validate the preferences."""
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "energy/validate"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == {
        "energy_sources": [],
        "device_consumption": [],
    }


async def test_get_solar_forecast(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, mock_energy_platform
) -> None:
    """Test we get preferences."""
    entry = MockConfigEntry(domain="some_domain")
    entry.add_to_hass(hass)

    manager = await data.async_get_manager(hass)

    manager.data = data.EnergyManager.default_preferences()
    manager.data["energy_sources"].append(
        {
            "type": "solar",
            "stat_energy_from": "my_solar_production",
            "config_entry_solar_forecast": [entry.entry_id],
        }
    )
    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json({"id": 5, "type": "energy/solar_forecast"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == {
        entry.entry_id: {
            "wh_hours": {
                "2021-06-27T13:00:00+00:00": 12,
                "2021-06-27T14:00:00+00:00": 8,
            }
        }
    }


@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
async def test_fossil_energy_consumption_no_co2(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test fossil_energy_consumption when co2 data is missing."""
    now = dt_util.utcnow()
    later = dt_util.as_utc(dt_util.parse_datetime("2022-09-01 00:00:00"))

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period2_day_start = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 00:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))
    period4_day_start = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 00:00:00"))

    external_energy_statistics_1 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_2 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 20,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 30,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 50,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 80,
        },
    )
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(
        hass, external_energy_metadata_1, external_energy_statistics_1
    )
    async_add_external_statistics(
        hass, external_energy_metadata_2, external_energy_statistics_2
    )
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(22.0),
        period2.isoformat(): pytest.approx(33.0 - 22.0),
        period3.isoformat(): pytest.approx(55.0 - 33.0),
        period4.isoformat(): pytest.approx(88.0 - 55.0),
    }

    await client.send_json(
        {
            "id": 2,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "day",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(22.0),
        period2_day_start.isoformat(): pytest.approx(33.0 - 22.0),
        period3.isoformat(): pytest.approx(55.0 - 33.0),
        period4_day_start.isoformat(): pytest.approx(88.0 - 55.0),
    }

    await client.send_json(
        {
            "id": 3,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "month",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(33.0),
        period3.isoformat(): pytest.approx((55.0 - 33.0) + (88.0 - 55.0)),
    }


@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
async def test_fossil_energy_consumption_hole(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test fossil_energy_consumption when some data points lack sum."""
    now = dt_util.utcnow()
    later = dt_util.as_utc(dt_util.parse_datetime("2022-09-01 00:00:00"))

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period2_day_start = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 00:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))
    period4_day_start = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 00:00:00"))

    external_energy_statistics_1 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": None,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_2 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 20,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": None,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 50,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 80,
        },
    )
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(
        hass, external_energy_metadata_1, external_energy_statistics_1
    )
    async_add_external_statistics(
        hass, external_energy_metadata_2, external_energy_statistics_2
    )
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(20.0),
        period2.isoformat(): pytest.approx(3.0),
        period3.isoformat(): pytest.approx(32.0),
        period4.isoformat(): pytest.approx(88.0 - 55.0),
    }

    await client.send_json(
        {
            "id": 2,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "day",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(20.0),
        period2_day_start.isoformat(): pytest.approx(3.0),
        period3.isoformat(): pytest.approx(32.0),
        period4_day_start.isoformat(): pytest.approx(88.0 - 55.0),
    }

    await client.send_json(
        {
            "id": 3,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "month",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(23.0),
        period3.isoformat(): pytest.approx((55.0 - 3.0) + (88.0 - 55.0) - 20.0),
    }


@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
async def test_fossil_energy_consumption_no_data(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test fossil_energy_consumption when there is no data."""
    now = dt_util.utcnow()
    later = dt_util.as_utc(dt_util.parse_datetime("2022-09-01 00:00:00"))

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))

    external_energy_statistics_1 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": None,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_2 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 20,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": None,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 50,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 80,
        },
    )
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(
        hass, external_energy_metadata_1, external_energy_statistics_1
    )
    async_add_external_statistics(
        hass, external_energy_metadata_2, external_energy_statistics_2
    )
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1_missing",
                "test:total_energy_import_tariff_2_missing",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {
            "id": 2,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1_missing",
                "test:total_energy_import_tariff_2_missing",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "day",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {
            "id": 3,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1_missing",
                "test:total_energy_import_tariff_2_missing",
            ],
            "co2_statistic_id": "test:co2_ratio_missing",
            "period": "month",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}


@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
async def test_fossil_energy_consumption(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test fossil_energy_consumption with co2 sensor data."""
    now = dt_util.utcnow()
    later = dt_util.as_utc(dt_util.parse_datetime("2022-09-01 00:00:00"))

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period2_day_start = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 00:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))
    period4_day_start = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 00:00:00"))

    external_energy_statistics_1 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 4,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_2 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 20000,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 30000,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 40000,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 50000,
        },
    )
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "Wh",
    }
    external_co2_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "mean": 10,
        },
        {
            "start": period2,
            "last_reset": None,
            "mean": 30,
        },
        {
            "start": period3,
            "last_reset": None,
            "mean": 60,
        },
        {
            "start": period4,
            "last_reset": None,
            "mean": 90,
        },
    )
    external_co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    async_add_external_statistics(
        hass, external_energy_metadata_1, external_energy_statistics_1
    )
    async_add_external_statistics(
        hass, external_energy_metadata_2, external_energy_statistics_2
    )
    async_add_external_statistics(hass, external_co2_metadata, external_co2_statistics)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:fossil_percentage",
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(11.0 * 0.2),
        period2.isoformat(): pytest.approx((33.0 - 22.0) * 0.3),
        period3.isoformat(): pytest.approx((44.0 - 33.0) * 0.6),
        period4.isoformat(): pytest.approx((55.0 - 44.0) * 0.9),
    }

    await client.send_json(
        {
            "id": 2,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:fossil_percentage",
            "period": "day",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(11.0 * 0.2),
        period2_day_start.isoformat(): pytest.approx((33.0 - 22.0) * 0.3),
        period3.isoformat(): pytest.approx((44.0 - 33.0) * 0.6),
        period4_day_start.isoformat(): pytest.approx((55.0 - 44.0) * 0.9),
    }

    await client.send_json(
        {
            "id": 3,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:fossil_percentage",
            "period": "month",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        period1.isoformat(): pytest.approx(11.0 * 0.5),
        period3.isoformat(): pytest.approx(
            ((44.0 - 33.0) * 0.6) + ((55.0 - 44.0) * 0.9)
        ),
    }


async def test_fossil_energy_consumption_checks(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test fossil_energy_consumption parameter validation."""
    client = await hass_ws_client(hass)
    now = dt_util.utcnow()

    await client.send_json(
        {
            "id": 1,
            "type": "energy/fossil_energy_consumption",
            "start_time": "donald_duck",
            "end_time": now.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:fossil_percentage",
            "period": "hour",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 1
    assert not msg["success"]
    assert msg["error"] == {
        "code": "invalid_start_time",
        "message": "Invalid start_time",
    }

    await client.send_json(
        {
            "id": 2,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": "donald_duck",
            "energy_statistic_ids": [
                "test:total_energy_import_tariff_1",
                "test:total_energy_import_tariff_2",
            ],
            "co2_statistic_id": "test:fossil_percentage",
            "period": "hour",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 2
    assert not msg["success"]
    assert msg["error"] == {"code": "invalid_end_time", "message": "Invalid end_time"}


@pytest.mark.freeze_time("2021-08-01 01:00:00+00:00")
async def test_fossil_energy_consumption_check_missing_hour(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test explicitly if the API keeps the first hour of data for the requested time frame."""

    now = dt_util.utcnow()
    later = dt_util.as_utc(dt_util.parse_datetime("2021-08-01 05:00:00"))

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    hour1 = dt_util.as_utc(dt_util.parse_datetime("2021-08-01 01:00:00"))
    hour2 = dt_util.as_utc(dt_util.parse_datetime("2021-08-01 02:00:00"))
    hour3 = dt_util.as_utc(dt_util.parse_datetime("2021-08-01 03:00:00"))
    hour4 = dt_util.as_utc(dt_util.parse_datetime("2021-08-01 04:00:00"))

    # add energy statistics for 4 hours
    energy_statistics_1 = (
        {
            "start": hour1,
            "last_reset": None,
            "state": 0,
            "sum": 1,
        },
        {
            "start": hour2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": hour3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": hour4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, energy_metadata_1, energy_statistics_1)

    # add co2 statistics for 4 hours
    co2_statistics = (
        {
            "start": hour1,
            "last_reset": None,
            "mean": 10,
        },
        {
            "start": hour2,
            "last_reset": None,
            "mean": 30,
        },
        {
            "start": hour3,
            "last_reset": None,
            "mean": 60,
        },
        {
            "start": hour4,
            "last_reset": None,
            "mean": 90,
        },
    )
    co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    async_add_external_statistics(hass, co2_metadata, co2_statistics)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "energy/fossil_energy_consumption",
            "start_time": now.isoformat(),
            "end_time": later.isoformat(),
            "energy_statistic_ids": [
                "test:total_energy_import",
            ],
            "co2_statistic_id": "test:fossil_percentage",
            "period": "hour",
        }
    )

    # check if we received deltas for the requested time frame
    response = await client.receive_json()
    assert response["success"]
    assert list(response["result"].keys()) == [
        hour1.isoformat(),
        hour2.isoformat(),
        hour3.isoformat(),
        hour4.isoformat(),
    ]
