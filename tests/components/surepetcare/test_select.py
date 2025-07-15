"""The tests for the Sure Petcare select platform."""

import pytest

from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HOUSEHOLD_ID, MOCK_API_DATA, MOCK_PET

from tests.common import MockConfigEntry

EXPECTED_ENTITY_IDS = {
    "select.pet": f"{HOUSEHOLD_ID}-24680",
}


async def test_no_select(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test that no select is created if not configured."""
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id not in state_entity_ids


@pytest.mark.parametrize(
    "mock_config_entry_setup",
    [
        {
            "with_pet_select": True,
        }
    ],
    indirect=True,
)
async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test the generation of unique ids."""
    state_entity_ids = hass.states.async_entity_ids()

    for entity_id, unique_id in EXPECTED_ENTITY_IDS.items():
        assert entity_id in state_entity_ids
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "Home"

        attr = state.attributes
        assert attr["options"] == [
            "Garage",
            "Home",
            "Outside",
        ]
        assert attr["last_seen_device_id"] == "13576"
        assert attr["last_update_type"] == "auto"
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == unique_id


@pytest.mark.parametrize(
    "mock_config_entry_setup",
    [
        {
            "with_pet_select": True,
        }
    ],
    indirect=True,
)
async def test_select_then_location_change(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test that select state changes when location changes."""

    state = hass.states.get("select.pet")
    assert state.state == "Home"

    surepetcare.set_call_response(
        {
            "data": {
                **MOCK_API_DATA,
                "pets": [
                    {
                        **MOCK_PET,
                        "position": {
                            "since": "2020-08-23T23:30:00",
                            "where": 1,
                            "device_id": 13579,
                        },
                    }
                ],
            }
        }
    )

    coordinator = hass.data[DOMAIN][mock_config_entry_setup.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    # select state should change because the mock surepetcare api
    # response has changed.
    state = hass.states.get("select.pet")
    assert state.state == "Garage"


@pytest.mark.parametrize(
    "mock_config_entry_setup",
    [
        {
            "with_pet_select": True,
        }
    ],
    indirect=True,
)
async def test_select_app_manually_set_location(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test that select state is correct when the location is manually set through the app."""

    state = hass.states.get("select.pet")
    assert state.state == "Home"

    surepetcare.set_call_response(
        {
            "data": {
                **MOCK_API_DATA,
                "pets": [
                    {
                        **MOCK_PET,
                        "position": {
                            "since": "2020-08-23T23:30:00",
                            "where": 2,
                            "user_id": 1,
                        },
                    }
                ],
            }
        }
    )

    coordinator = hass.data[DOMAIN][mock_config_entry_setup.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    # select state should change because the mock surepetcare api
    # response has changed.
    state = hass.states.get("select.pet")
    assert state.state == "Outside"


@pytest.mark.parametrize(
    "mock_config_entry_setup",
    [
        {
            "with_pet_select": True,
        }
    ],
    indirect=True,
)
async def test_select_manual_update(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test select manual update."""
    await hass.services.async_call(
        "select",
        "select_option",
        service_data={"option": "Garage"},
        blocking=True,
        target={"entity_id": "select.pet"},
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.pet")
    assert state.state == "Garage"

    attr = state.attributes
    assert attr["last_update_type"] == "manual"

    coordinator = hass.data[DOMAIN][mock_config_entry_setup.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    # select state should not change because it was set manually
    # and the mock surepetcare api response has not changed.
    state = hass.states.get("select.pet")
    assert state.state == "Garage"

    attr = state.attributes
    assert attr["last_update_type"] == "manual"


@pytest.mark.parametrize(
    "mock_config_entry_setup",
    [
        {
            "with_pet_select": True,
        }
    ],
    indirect=True,
)
async def test_select_manual_update_then_location_change(
    hass: HomeAssistant,
    surepetcare,
    mock_config_entry_setup: MockConfigEntry,
) -> None:
    """Test that select state changes when location changes after manual update."""
    await hass.services.async_call(
        "select",
        "select_option",
        service_data={"option": "Outside"},
        blocking=True,
        target={"entity_id": "select.pet"},
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.pet")
    assert state.state == "Outside"

    attr = state.attributes
    assert attr["last_update_type"] == "manual"

    surepetcare.set_call_response(
        {
            "data": {
                **MOCK_API_DATA,
                "pets": [
                    {
                        **MOCK_PET,
                        "position": {
                            "since": "2020-08-23T23:30:00",
                            "where": 1,
                            "device_id": 13579,
                        },
                    }
                ],
            }
        }
    )

    coordinator = hass.data[DOMAIN][mock_config_entry_setup.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    # select state should change because the mock surepetcare api
    # response has changed.
    state = hass.states.get("select.pet")
    assert state.state == "Garage"

    attr = state.attributes
    assert attr["last_update_type"] == "auto"
