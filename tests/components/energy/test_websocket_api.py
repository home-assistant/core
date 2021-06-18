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


async def test_get_preferences(hass, hass_ws_client, hass_storage) -> None:
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

    new_prefs = {
        "stat_house_energy_meter": "mock_stat_house",
        "stat_solar_generatation": "mock_stat_solar_gen",
        "stat_solar_return_to_grid": "mock_stat_solar_grid",
        "stat_solar_predicted_generation": "mock_stat_solar_predict",
        "stat_device_consumption": ["mock_stat_dev_cons"],
        "schedule_tariff": None,
        "cost_kwh_low_tariff": 2,
        "cost_kwh_normal_tariff": 3,
        "cost_grid_management_day": 4,
        "cost_delivery_cost_day": 5,
        "cost_discount_energy_tax_day": 6,
    }

    await client.send_json({"id": 5, "type": "energy/save_prefs", **new_prefs})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == new_prefs

    assert data.STORAGE_KEY not in hass_storage, "expected not to be written yet"

    await flush_store(hass.data[data.DOMAIN]._store)

    assert hass_storage[data.STORAGE_KEY]["data"] == new_prefs
