"""Test the Legrand Home+ Control integration."""
import asyncio
from unittest.mock import patch

from homepluscontrol.homeplusplant import (
    PLANT_TOPOLOGY_BASE_URL,
    PLANT_TOPOLOGY_RESOURCE,
)

from homeassistant import config_entries, setup
from homeassistant.components.homepluscontrol import api
from homeassistant.components.homepluscontrol.const import DOMAIN, PLANT_URL


async def entity_assertions(
    hass,
    num_exp_entities,
    num_exp_devices=None,
    coordinator=None,
    expected_entities=None,
    expected_devices=None,
):
    """Assert number of entities and devices."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()

    if coordinator is None:
        coordinator = hass.data["homepluscontrol"][
            "homepluscontrol_entry_id_coordinator"
        ]

    if num_exp_devices is None:
        num_exp_devices = num_exp_entities

    assert len(hass.data[DOMAIN]["entities"].keys()) == num_exp_entities
    if coordinator.data is not None:
        assert len(coordinator.data.keys()) == num_exp_entities
    assert len(entity_reg.entities.keys()) == num_exp_entities
    assert len(device_reg.devices.keys()) == num_exp_devices

    if expected_entities is not None:
        for exp_entity, present in expected_entities.items():
            assert bool(entity_reg.async_get(exp_entity)) == present

    if expected_devices is not None:
        for exp_device, present in expected_devices.items():
            assert bool(device_reg.async_get(exp_device)) == present


async def test_loading(hass, mock_config_entry):
    """Test component loading."""
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await setup.async_setup_component(hass, "homepluscontrol", {})

    await mock_config_entry.async_setup(hass)
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert mock_config_entry.state == config_entries.ENTRY_STATE_LOADED


async def test_plant_update(
    hass, aioclient_mock, mock_config_entry, plant_data, plant_topology, plant_modules
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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )


async def test_plant_topology_reduction_change(
    hass,
    aioclient_mock,
    mock_config_entry,
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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices - 5 mock entities
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

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

    # Need to patch the API to ignore the refresh interval settings
    with patch(
        "homeassistant.components.homepluscontrol.api.HomePlusControlAsyncApi._should_check",
        return_value=True,
    ) as mock_check:
        coordinator = hass.data["homepluscontrol"][
            "homepluscontrol_entry_id_coordinator"
        ]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(mock_check.mock_calls) == 3

    # Check for plant, topology and module status - this time only 4 left
    await entity_assertions(
        hass,
        num_exp_entities=4,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": False,
        },
    )


async def test_plant_topology_increase_change(
    hass,
    aioclient_mock,
    mock_config_entry,
    plant_data,
    plant_topology,
    plant_modules,
    plant_topology_reduced,
    plant_modules_reduced,
):
    """Test an entity entering the plant topology."""

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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices - we have 4 entities to start with
    await entity_assertions(
        hass,
        num_exp_entities=4,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": False,
        },
    )

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
        assert len(mock_check.mock_calls) == 3
    # Check for plant, topology and module status
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )


async def test_module_status_reduction_change(
    hass,
    aioclient_mock,
    mock_config_entry,
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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices - 5 entities
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Confirm the availability of this particular entity
    test_entity = hass.data[DOMAIN]["entities"].get("0000000987654321fedcba")
    assert test_entity.available

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
        assert len(mock_check.mock_calls) == 3
    # Check for plant, topology and module status
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # This entity is present, but not available
    test_entity = hass.data[DOMAIN]["entities"].get("0000000987654321fedcba")
    assert test_entity
    assert not test_entity.available


async def test_module_status_increase_change(
    hass,
    aioclient_mock,
    mock_config_entry,
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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # Check the entities and devices
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # This particular entity is not available
    test_entity = hass.data[DOMAIN]["entities"].get("0000000987654321fedcba")
    assert test_entity
    assert not test_entity.available

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
        assert len(mock_check.mock_calls) == 3
    # Check for plant, topology and module status
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Now the entity is available
    test_entity = hass.data[DOMAIN]["entities"].get("0000000987654321fedcba")
    assert test_entity
    assert test_entity.available


async def test_plant_api_timeout(
    hass, aioclient_mock, mock_config_entry, plant_data, plant_topology, plant_modules
):
    """Test an API timeout when loading the plant data."""

    # Register the mock responses
    aioclient_mock.get(
        PLANT_URL,
        text=plant_data,
        exc=asyncio.TimeoutError,
    )

    # Load the entry
    hass.data[DOMAIN] = {}
    hass.config.components.add(DOMAIN)
    config_entry = mock_config_entry
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
    await entity_assertions(hass, num_exp_entities=0)


async def test_plant_topology_api_timeout(
    hass, aioclient_mock, mock_config_entry, plant_data, plant_topology, plant_modules
):
    """Test an API timeout when loading the plant topology data."""

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
    config_entry = mock_config_entry
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
    await entity_assertions(hass, num_exp_entities=0)


async def test_plant_status_api_timeout(
    hass, aioclient_mock, mock_config_entry, plant_data, plant_topology, plant_modules
):
    """Test an API timeout when loading the plant module status data."""

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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times - fails on plant status update
    assert aioclient_mock.call_count == 3

    # The component has been loaded
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    # Check the entities and devices - all entities should be there, but not available
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )
    for test_entity in hass.data[DOMAIN]["entities"].values():
        assert test_entity
        assert not test_entity.available


async def test_update_with_plant_topology_api_timeout(
    hass,
    aioclient_mock,
    mock_config_entry,
    plant_data,
    plant_topology,
    plant_modules,
    plant_topology_reduced,
    plant_modules_reduced,
):
    """Test an API timeout when updating the plant topology data.

    In the update the plant topology is reduced by 1 module, so we test whether this is handled gracefully.
    """

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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # The component has been loaded
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    # Check the entities and devices - all entities should be there
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )
    for test_entity in hass.data[DOMAIN]["entities"].values():
        assert test_entity.available

    # Attempt to update the data, but plant topology update fails

    # Reset the mock responses
    aioclient_mock.clear_requests()
    # Register the mock responses
    aioclient_mock.get(
        PLANT_URL,
        text=plant_data,
    )
    aioclient_mock.get(
        PLANT_TOPOLOGY_BASE_URL + "123456789009876543210" + PLANT_TOPOLOGY_RESOURCE,
        text=plant_topology_reduced,
        exc=asyncio.TimeoutError,
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
        assert len(mock_check.mock_calls) == 3

    # Check for plant, topology and module status
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # This entity has not returned a status, so appears as unavailable
    test_entity = hass.data[DOMAIN]["entities"].get("0000000987654321fedcba")
    assert test_entity
    assert not test_entity.available


async def test_update_with_plant_module_status_api_timeout(
    hass,
    aioclient_mock,
    mock_config_entry,
    plant_data,
    plant_topology,
    plant_modules,
    plant_topology_reduced,
    plant_modules_reduced,
):
    """Test an API timeout when updating the plant module status data.

    In the update the plant topology is increased by 1 module, so we test whether this is handled gracefully.
    """

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
    config_entry = mock_config_entry
    await setup.async_setup_component(hass, "http", {})
    assert hass.http.app
    await config_entry.async_setup(hass)
    await hass.async_block_till_done()

    # The setup of the integration calls the API 3 times
    assert aioclient_mock.call_count == 3

    # The component has been loaded
    assert isinstance(
        hass.data[DOMAIN]["homepluscontrol_entry_id"], api.HomePlusControlAsyncApi
    )
    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    # Check the entities and devices - all entities should be there
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    assert len(hass.data[DOMAIN]["entities"].keys()) == 4
    for test_entity in hass.data[DOMAIN]["entities"].values():
        assert test_entity.available
    assert len(entity_reg.entities.keys()) == 4
    assert len(device_reg.devices.keys()) == 4

    # Attempt to update the data, but plant topology update fails

    # Reset the mock responses
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
        exc=asyncio.TimeoutError,
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
        assert len(mock_check.mock_calls) == 3

    # Check for plant, topology and module status
    await entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # One entity has no status data, so appears as unavailable
    # The rest of the entities remain available
    for test_entity in hass.data[DOMAIN]["entities"].values():
        if test_entity.unique_id == "0000000987654321fedcba":
            assert not test_entity.available
        else:
            assert test_entity.available
