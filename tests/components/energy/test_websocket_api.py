"""Test the Energy websocket API."""
import pytest

from homeassistant.components.energy import data
from homeassistant.setup import async_setup_component

from tests.common import flush_store


@pytest.fixture(autouse=True)
async def setup_integration(hass):
    """Set up the integration."""
    assert await async_setup_component(
        hass, "energy", {"recorder": {"db_url": "sqlite://"}}
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
    manager = await data.async_get_manager(hass)
    manager.data = data.EnergyManager.default_preferences()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "energy/get_prefs"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == data.EnergyManager.default_preferences()


async def test_save_preferences(hass, hass_ws_client, hass_storage) -> None:
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
        "currency": "$",
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
                        "stat_energy_to": "sensor.return_to_grid",
                        "stat_compensation": None,
                        "entity_energy_to": None,
                        "entity_energy_price": None,
                        "number_energy_price": None,
                    },
                    {
                        "stat_energy_to": "return_to_grid_stat",
                        "stat_compensation": None,
                        "entity_energy_to": "sensor.return_to_grid",
                        "entity_energy_price": None,
                        "number_energy_price": 0.20,
                    },
                ],
                "cost_adjustment_day": 1.2,
            },
            {
                "type": "solar",
                "stat_energy_from": "my_solar_production",
                "config_entry_solar_forecast": "predicted_stat",
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

    await flush_store(hass.data[data.DOMAIN]._store)

    assert hass_storage[data.STORAGE_KEY]["data"] == new_prefs

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

    await client.send_json({"id": 7, "type": "energy/save_prefs", **new_prefs_2})

    msg = await client.receive_json()

    assert msg["id"] == 7
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
