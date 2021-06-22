"""Test the Energy config flow."""
import pytest

from homeassistant.components.energy import data
from homeassistant.setup import async_setup_component

from tests.common import flush_store


@pytest.fixture(autouse=True)
async def setup_integration(hass):
    """Set up the integration."""
    assert await async_setup_component(hass, "energy", {})


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
    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": data.EnergyManager.default_preferences(),
    }

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
        "home_consumption": [
            {
                "stat_consumption": "heat_pump_meter",
                "stat_tariff": "heat_pump_kwh_cost",
                "cost_management_day": 1.2,
                "cost_delivery_cost_day": 3.4,
                "discount_energy_tax_day": 5.6,
            },
            {
                "stat_consumption": "home_meter",
                "stat_tariff": None,
                "cost_management_day": 0,
                "cost_delivery_cost_day": 0,
                "discount_energy_tax_day": 0,
            },
        ],
        "device_consumption": [{"stat_consumption": "some_device_usage"}],
        "production": [
            {
                "type": "solar",
                "stat_generation": "my_solar_generation",
                "stat_return_to_grid": "returned_to_grid_stat",
                "stat_predicted_generation": "predicted_stat",
            },
            {
                "type": "wind",
                "stat_generation": "my_wind_geneeration",
                "stat_return_to_grid": None,
                "stat_predicted_generation": None,
            },
        ],
    }

    await client.send_json({"id": 6, "type": "energy/save_prefs", **new_prefs})

    msg = await client.receive_json()

    assert msg["id"] == 6
    assert msg["success"]
    assert msg["result"] == new_prefs

    assert data.STORAGE_KEY not in hass_storage, "expected not to be written yet"

    await flush_store(hass.data[data.DOMAIN]._store)

    assert hass_storage[data.STORAGE_KEY]["data"] == new_prefs
