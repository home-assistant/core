"""Test the Legrand Home+ Control switch platform."""
import datetime as dt
from unittest.mock import patch

from homepluscontrol.homeplusapi import HomePlusControlApiError

from homeassistant import config_entries, setup
from homeassistant.components.home_plus_control.const import (
    CONF_SUBSCRIPTION_KEY,
    DOMAIN,
)
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import CLIENT_ID, CLIENT_SECRET, SUBSCRIPTION_KEY

from tests.common import async_fire_time_changed


def entity_assertions(
    hass,
    num_exp_entities,
    num_exp_devices=None,
    expected_entities=None,
    expected_devices=None,
):
    """Assert number of entities and devices."""
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    if num_exp_devices is None:
        num_exp_devices = num_exp_entities

    assert len(entity_reg.entities) == num_exp_entities
    assert len(device_reg.devices) == num_exp_devices

    if expected_entities is not None:
        for exp_entity_id, present in expected_entities.items():
            assert bool(entity_reg.async_get(exp_entity_id)) == present

    if expected_devices is not None:
        for exp_device_id, present in expected_devices.items():
            assert bool(device_reg.async_get(exp_device_id)) == present


def one_entity_state(hass, device_uid):
    """Assert the presence of an entity and return its state."""
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    device_id = device_reg.async_get_device({(DOMAIN, device_uid)}).id
    entity_entries = er.async_entries_for_device(entity_reg, device_id)

    assert len(entity_entries) == 1
    entity_entry = entity_entries[0]
    return hass.states.get(entity_entry.entity_id).state


async def test_plant_update(
    hass: HomeAssistant,
    mock_config_entry,
    mock_modules,
) -> None:
    """Test entity and device loading."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )


async def test_plant_topology_reduction_change(
    hass: HomeAssistant,
    mock_config_entry,
    mock_modules,
) -> None:
    """Test an entity leaving the plant topology."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices - 5 mock entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Now we refresh the topology with one entity less
    mock_modules.pop("0000000987654321fedcba")
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=400)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check for plant, topology and module status - this time only 4 left
    entity_assertions(
        hass,
        num_exp_entities=4,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": False,
        },
    )


async def test_plant_topology_increase_change(
    hass: HomeAssistant,
    mock_config_entry,
    mock_modules,
) -> None:
    """Test an entity entering the plant topology."""
    # Remove one module initially
    new_module = mock_modules.pop("0000000987654321fedcba")

    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices - we have 4 entities to start with
    entity_assertions(
        hass,
        num_exp_entities=4,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": False,
        },
    )

    # Now we refresh the topology with one entity more
    mock_modules["0000000987654321fedcba"] = new_module
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=400)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )


async def test_module_status_unavailable(
    hass: HomeAssistant, mock_config_entry, mock_modules
) -> None:
    """Test a module becoming unreachable in the plant."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Check the entities and devices - 5 mock entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Confirm the availability of this particular entity
    test_entity_uid = "0000000987654321fedcba"
    test_entity_state = one_entity_state(hass, test_entity_uid)
    assert test_entity_state == STATE_ON

    # Now we refresh the topology with the module being unreachable
    mock_modules["0000000987654321fedcba"].reachable = False

    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=400)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )
    await hass.async_block_till_done()
    # The entity is present, but not available
    test_entity_state = one_entity_state(hass, test_entity_uid)
    assert test_entity_state == STATE_UNAVAILABLE


async def test_module_status_available(
    hass: HomeAssistant,
    mock_config_entry,
    mock_modules,
) -> None:
    """Test a module becoming reachable in the plant."""
    # Set the module initially unreachable
    mock_modules["0000000987654321fedcba"].reachable = False

    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # This particular entity is not available
    test_entity_uid = "0000000987654321fedcba"
    test_entity_state = one_entity_state(hass, test_entity_uid)
    assert test_entity_state == STATE_UNAVAILABLE

    # Now we refresh the topology with the module being reachable
    mock_modules["0000000987654321fedcba"].reachable = True
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=400)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities remain the same
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # Now the entity is available
    test_entity_uid = "0000000987654321fedcba"
    test_entity_state = one_entity_state(hass, test_entity_uid)
    assert test_entity_state == STATE_ON


async def test_initial_api_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_modules,
) -> None:
    """Test an API error on initial call."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
        side_effect=HomePlusControlApiError,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # The component has been loaded
    assert mock_config_entry.state is config_entries.ConfigEntryState.LOADED

    # Check the entities and devices - None have been configured
    entity_assertions(hass, num_exp_entities=0)


async def test_update_with_api_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_modules,
) -> None:
    """Test an API timeout when updating the module data."""
    # Load the entry
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
    ) as mock_check:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "home_plus_control": {
                    CONF_CLIENT_ID: CLIENT_ID,
                    CONF_CLIENT_SECRET: CLIENT_SECRET,
                    CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
                },
            },
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # The component has been loaded
    assert mock_config_entry.state is config_entries.ConfigEntryState.LOADED

    # Check the entities and devices - all entities should be there
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )
    for test_entity_uid in mock_modules:
        test_entity_state = one_entity_state(hass, test_entity_uid)
        assert test_entity_state in (STATE_ON, STATE_OFF)

    # Attempt to update the data, but API update fails
    with patch(
        "homeassistant.components.home_plus_control.api.HomePlusControlAsyncApi.async_get_modules",
        return_value=mock_modules,
        side_effect=HomePlusControlApiError,
    ) as mock_check:
        async_fire_time_changed(
            hass, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=400)
        )
        await hass.async_block_till_done()
    assert len(mock_check.mock_calls) == 1

    # Assert the devices and entities - all should still be present
    entity_assertions(
        hass,
        num_exp_entities=5,
        expected_entities={
            "switch.dining_room_wall_outlet": True,
            "switch.kitchen_wall_outlet": True,
        },
    )

    # This entity has not returned a status, so appears as unavailable
    for test_entity_uid in mock_modules:
        test_entity_state = one_entity_state(hass, test_entity_uid)
        assert test_entity_state == STATE_UNAVAILABLE
