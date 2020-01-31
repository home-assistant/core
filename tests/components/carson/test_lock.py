"""Tests for the Carson Lock platform."""
from unittest.mock import patch

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN

from .common import CARSON_API_VERSION, carson_load_fixture, setup_platform


async def test_entity_registry(hass, success_requests_mock):
    """Tests that the devices are registed in the entity registry."""
    await setup_platform(hass, LOCK_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("lock.door_1")
    assert entry.unique_id == "carson_door_21"

    entry = entity_registry.async_get("lock.door_2")
    assert entry.unique_id == "carson_door_22"

    entry = entity_registry.async_get("lock.door_3")
    assert entry.unique_id == "carson_door_23"


async def test_lock_reports_correct_initial_values(hass, success_requests_mock):
    """Tests that the initial state of a lock is correct."""
    await setup_platform(hass, LOCK_DOMAIN)

    state = hass.states.get("lock.door_1")
    assert state.state == "locked"
    assert state.attributes.get("friendly_name") == "Door 1"
    assert state.attributes.get("provider") == "smartair"
    assert state.attributes.get("is_active")
    assert not state.attributes.get("disabled")
    assert not state.attributes.get("is_unit_door")
    assert not state.attributes.get("staff_only")
    assert state.attributes.get("default_in_building")
    assert state.attributes.get("external_id") == "204"
    assert state.attributes.get("available")


async def test_lock_can_be_opened(hass, success_requests_mock):
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, LOCK_DOMAIN)

    state = hass.states.get("lock.door_1")
    assert state.state == "locked"

    success_requests_mock.post(
        f"https://api.carson.live/api/v{CARSON_API_VERSION}/doors/21/open/",
        text=carson_load_fixture("carson_door_open.json"),
    )

    # reduce unlock timespan to 0 to not hold test.
    with patch(
        "homeassistant.components.carson.lock.CarsonLock._unlocked_timespan",
        return_value=0,
    ) as mock_timespan:
        await hass.services.async_call("lock", "open", {"entity_id": "lock.door_1"})

        # since the unlocked timespan is 0 an unlock state cannot be tested for.
        await hass.async_block_till_done()

        assert len(mock_timespan.mock_calls) == 1
        state = hass.states.get("lock.door_1")
        assert state.state == "locked"


async def test_lock_can_be_updated(hass, success_requests_mock):
    """Test that the lock state is updated in HA."""
    await setup_platform(hass, LOCK_DOMAIN)

    state = hass.states.get("lock.door_1")
    assert state.attributes.get("provider") == "smartair"

    success_requests_mock.get(
        f"https://api.carson.live/api/v{CARSON_API_VERSION}/me/",
        text=carson_load_fixture("carson_me_update.json"),
    )

    await hass.services.async_call("carson", "update", {})

    await hass.async_block_till_done()

    state = hass.states.get("lock.door_1")
    assert state.attributes.get("provider") == "new_provider"
