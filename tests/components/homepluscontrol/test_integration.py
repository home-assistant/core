"""Test the Legrand Home+ Control integration."""
import asyncio

from homepluscontrol.homeplusplant import (
    PLANT_TOPOLOGY_BASE_URL,
    PLANT_TOPOLOGY_RESOURCE,
)

from homeassistant import config_entries, setup
from homeassistant.components.homepluscontrol import api
from homeassistant.components.homepluscontrol.const import DOMAIN, PLANT_URL

from tests.async_mock import patch

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

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert entity_reg.async_get("switch.dining_room_wall_outlet")
    assert len(entity_reg.entities.keys()) == 5
    assert len(device_reg.devices.keys()) == 5


async def test_plant_topology_reduction_change(
    hass,
    aioclient_mock,
    plant_data,
    plant_topology,
    plant_modules,
    plant_topology_reduced,
):
    """Test an entity leaving the plant topology."""

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

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert entity_reg.async_get("switch.dining_room_wall_outlet")
    assert len(entity_reg.entities.keys()) == 5
    assert len(device_reg.devices.keys()) == 5

    # Now we refresh the topology with one entity less
    aioclient_mock.clear_requests()
    # Register the mock responses
    aioclient_mock.get(
        PLANT_URL,
        text=plant_data,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210" + PLANT_TOPOLOGY_RESOURCE,
        text=plant_topology_reduced,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210",
        text=plant_modules,
    )

    with patch(
        "homeassistant.components.homepluscontrol.api.HomePlusControlAsyncApi._should_check",
        return_value=True,
    ) as mock_check:
        coordinator = hass.data["homepluscontrol"][
            "homepluscontrol_entry_id_coordinator"
        ]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert (
            len(mock_check.mock_calls) == 3
        )  # Check for plant, topology and module status
        assert len(entity_reg.entities.keys()) == 4
        assert len(device_reg.devices.keys()) == 4


async def test_plant_topology_increase_change(
    hass,
    aioclient_mock,
    plant_data,
    plant_topology,
    plant_modules,
    plant_topology_reduced,
    plant_modules_reduced,
):
    """Test an entity leaving the plant topology."""

    # Register the mock responses
    aioclient_mock.get(
        PLANT_URL,
        text=plant_data,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210" + PLANT_TOPOLOGY_RESOURCE,
        text=plant_topology_reduced,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210",
        text=plant_modules_reduced,
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

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()

    assert entity_reg.async_get("switch.dining_room_wall_outlet")
    assert len(entity_reg.entities.keys()) == 4
    assert len(device_reg.devices.keys()) == 4

    # Now we refresh the topology with one entity more
    aioclient_mock.clear_requests()
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

    with patch(
        "homeassistant.components.homepluscontrol.api.HomePlusControlAsyncApi._should_check",
        return_value=True,
    ) as mock_check:
        coordinator = hass.data["homepluscontrol"][
            "homepluscontrol_entry_id_coordinator"
        ]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert (
            len(mock_check.mock_calls) == 3
        )  # Check for plant, topology and module status
        assert len(entity_reg.entities.keys()) == 5
        assert len(device_reg.devices.keys()) == 5


async def test_module_status_reduction_change(
    hass,
    aioclient_mock,
    plant_data,
    plant_topology,
    plant_modules,
    plant_modules_reduced,
):
    """Test a missing module status in the plant topology."""

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

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert entity_reg.async_get("switch.kitchen_wall_outlet")
    assert len(hass.data[DOMAIN]["entities"].keys()) == 5
    test_entity = hass.data[DOMAIN]["entities"]["0000000987654321fedcba"]
    assert test_entity
    assert test_entity.available
    assert len(entity_reg.entities.keys()) == 5
    assert len(device_reg.devices.keys()) == 5

    # Now we refresh the topology with one module status less
    aioclient_mock.clear_requests()
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
        text=plant_modules_reduced,
    )

    with patch(
        "homeassistant.components.homepluscontrol.api.HomePlusControlAsyncApi._should_check",
        return_value=True,
    ) as mock_check:
        coordinator = hass.data["homepluscontrol"][
            "homepluscontrol_entry_id_coordinator"
        ]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert (
            len(mock_check.mock_calls) == 3
        )  # Check for plant, topology and module status
        assert len(entity_reg.entities.keys()) == 5
        assert len(device_reg.devices.keys()) == 5

    assert test_entity
    assert not test_entity.available


async def test_module_status_increase_change(
    hass,
    aioclient_mock,
    plant_data,
    plant_topology,
    plant_modules,
    plant_modules_reduced,
):
    """Test a additional module status in the plant topology."""

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
        text=plant_modules_reduced,
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

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert entity_reg.async_get("switch.kitchen_wall_outlet")
    assert len(hass.data[DOMAIN]["entities"].keys()) == 5
    test_entity = hass.data[DOMAIN]["entities"]["0000000987654321fedcba"]
    assert test_entity
    assert not test_entity.available
    assert len(entity_reg.entities.keys()) == 5
    assert len(device_reg.devices.keys()) == 5

    # Now we refresh the topology with one module status more
    aioclient_mock.clear_requests()
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

    with patch(
        "homeassistant.components.homepluscontrol.api.HomePlusControlAsyncApi._should_check",
        return_value=True,
    ) as mock_check:
        coordinator = hass.data["homepluscontrol"][
            "homepluscontrol_entry_id_coordinator"
        ]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert (
            len(mock_check.mock_calls) == 3
        )  # Check for plant, topology and module status
        assert len(entity_reg.entities.keys()) == 5
        assert len(device_reg.devices.keys()) == 5

    assert test_entity
    assert test_entity.available


async def test_plant_api_timeout(
    hass, aioclient_mock, plant_data, plant_topology, plant_modules
):
    """Test an API timeout when loading the data initially."""

    # Register the mock responses
    aioclient_mock.get(
        PLANT_URL,
        text=plant_data,
        exc=asyncio.TimeoutError,
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

    # The setup of the integration calls the API 1 time only - fails on plant data update
    assert aioclient_mock.call_count == 1

    # The component has been loaded
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    # Check the entities and devices - None have been configured
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert len(entity_reg.entities.keys()) == 0
    assert len(device_reg.devices.keys()) == 0
    assert len(hass.data[DOMAIN]["entities"].keys()) == 0


async def test_plant_topology_api_timeout(
    hass, aioclient_mock, plant_data, plant_topology, plant_modules
):
    """Test an API timeout when loading the data initially."""

    # Register the mock responses
    aioclient_mock.get(
        PLANT_URL,
        text=plant_data,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210" + PLANT_TOPOLOGY_RESOURCE,
        text=plant_topology,
        exc=asyncio.TimeoutError,
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

    # The setup of the integration calls the API 2 times - fails on plant topology update
    assert aioclient_mock.call_count == 2

    # The component has been loaded
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    # Check the entities and devices - None have been configured
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert len(entity_reg.entities.keys()) == 0
    assert len(device_reg.devices.keys()) == 0
    assert len(hass.data[DOMAIN]["entities"].keys()) == 0


async def test_plant_status_api_timeout(
    hass, aioclient_mock, plant_data, plant_topology, plant_modules
):
    """Test an API timeout when loading the data initially."""

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
        exc=asyncio.TimeoutError,
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

    # The setup of the integration calls the API 1 time only - fails on plant data update
    assert aioclient_mock.call_count == 3

    # The component has been loaded
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    coordinator = hass.data["homepluscontrol"]["homepluscontrol_entry_id_coordinator"]

    # The setup of the integration calls the API 2 times - fails on plant status update
    # Plant data is cached already, so no call to API for that
    print(aioclient_mock.mock_calls)

    if coordinator.data and len(coordinator.data.keys()) > 0:
        for id, ent in coordinator.data.items():
            print("Coordinator item: " + id + ": " + str(ent))

    # Check the entities and devices - all entities should be there, but not available
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert len(hass.data[DOMAIN]["entities"].keys()) == 5
    for test_entity in hass.data[DOMAIN]["entities"].values():
        assert test_entity
        assert not test_entity.available
    assert len(entity_reg.entities.keys()) == 5
    assert len(device_reg.devices.keys()) == 4


async def test_update_api_timeout(hass, aioclient_mock):
    """Test timeouts during API updates."""
    pass
