"""Test the Legrand Home+ Control integration."""
from homepluscontrol.homeplusplant import (
    PLANT_TOPOLOGY_BASE_URL,
    PLANT_TOPOLOGY_RESOURCE,
)

from homeassistant import config_entries, setup
from homeassistant.components.homepluscontrol import api
from homeassistant.components.homepluscontrol.const import DOMAIN, PLANT_URL

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SUBSCRIPTION_KEY = "12345678901234567890123456789012"
REDIRECT_URI = "https://example.com:8213/auth/external/callback"


async def test_loading(hass):
    """Test component loading."""
    config_entry = config_entries.ConfigEntry(
        1,
        DOMAIN,
        "Home+ Control",
        {
            "auth_implementation": "homepluscontrol",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": 1608824371.2857926,
            },
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "subscription_key": SUBSCRIPTION_KEY,
            "redirect_uri": REDIRECT_URI,
        },
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={"disable_new_entities": False},
        unique_id=DOMAIN,
        entry_id="homepluscontrol_entry_id",
    )

    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await setup.async_setup_component(hass, "homepluscontrol", {})

    await config_entry.async_setup(hass)
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert config_entry.state == config_entries.ENTRY_STATE_LOADED


async def test_plant_update(
    hass, aioclient_mock, plant_data, plant_topology, plant_modules
):
    """Test entity and device loading."""

    # Register the mock responses
    aioclient_mock.get(
        PLANT_URL,
        text=plant_data,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210" + PLANT_TOPOLOGY_RESOURCE,
        text=plant_topology,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210",
        text=plant_modules,
    )

    # Load the entry
    hass.data[DOMAIN] = {}
    hass.config.components.add(DOMAIN)
    config_entry = config_entries.ConfigEntry(
        1,
        DOMAIN,
        "Home+ Control",
        {
            "auth_implementation": "homepluscontrol",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": 9608824371.2857926,
                "expires_on": 9608824371,
            },
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "subscription_key": SUBSCRIPTION_KEY,
            "redirect_uri": REDIRECT_URI,
        },
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={"disable_new_entities": False},
        unique_id=DOMAIN,
        entry_id="homepluscontrol_entry_id",
    )
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # Check the entities and devices
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert entity_reg.async_get("switch.dining_room_wall_outlet")
    assert len(entity_reg.entities.keys()) == 5
    assert len(device_reg.devices.keys()) == 5
