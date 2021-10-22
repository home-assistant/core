"""Test the Energy websocket API."""
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.energy import data, is_configured
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, flush_store, mock_platform


@pytest.fixture(autouse=True)
async def setup_integration(hass):
    """Set up the integration."""
    assert await async_setup_component(
        hass, "energy", {"recorder": {"db_url": "sqlite://"}}
    )


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


async def test_get_preferences_no_data(hass, hass_ws_client) -> None:
    """Test we get error if no preferences set."""
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "energy/get_prefs"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"] == {"code": "not_found", "message": "No prefs"}


async def test_get_preferences_default(hass, hass_ws_client, hass_storage) -> None:
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
    hass, hass_ws_client, hass_storage, mock_energy_platform
) -> None:
    """Test we can save preferences."""
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
                        "entity_energy_from": None,
                        "entity_energy_price": None,
                        "number_energy_price": None,
                    },
                    {
                        "stat_energy_from": "sensor.heat_pump_meter_2",
                        "stat_cost": None,
                        "entity_energy_from": "sensor.heat_pump_meter_2",
                        "entity_energy_price": None,
                        "number_energy_price": 0.20,
                    },
                ],
                "flow_to": [
                    {
                        "stat_energy_to": "sensor.return_to_grid_peak",
                        "stat_compensation": None,
                        "entity_energy_to": None,
                        "entity_energy_price": None,
                        "number_energy_price": None,
                    },
                    {
                        "stat_energy_to": "sensor.return_to_grid_offpeak",
                        "stat_compensation": None,
                        "entity_energy_to": "sensor.return_to_grid_offpeak",
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
            "sensor.return_to_grid_offpeak": "sensor.return_to_grid_offpeak_compensation",
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
                        "entity_energy_from": None,
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


async def test_handle_duplicate_from_stat(hass, hass_ws_client) -> None:
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
                            "entity_energy_from": None,
                            "entity_energy_price": None,
                            "number_energy_price": None,
                        },
                        {
                            "stat_energy_from": "sensor.heat_pump_meter",
                            "stat_cost": None,
                            "entity_energy_from": None,
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


async def test_validate(hass, hass_ws_client) -> None:
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


async def test_get_solar_forecast(hass, hass_ws_client, mock_energy_platform) -> None:
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
