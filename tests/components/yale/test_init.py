"""The tests for the yale platform."""

from unittest.mock import Mock

from aiohttp import ClientResponseError
import pytest
from yalexs.exceptions import InvalidAuth, YaleApiError

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.yale.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .mocks import (
    _create_yale_with_devices,
    _mock_doorsense_enabled_yale_lock_detail,
    _mock_doorsense_missing_yale_lock_detail,
    _mock_inoperative_yale_lock_detail,
    _mock_lock_with_offline_key,
    _mock_operative_yale_lock_detail,
)

from tests.typing import WebSocketGenerator


async def test_yale_api_is_failing(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when yale api is failing."""

    config_entry, socketio = await _create_yale_with_devices(
        hass,
        authenticate_side_effect=YaleApiError(
            "offline", ClientResponseError(None, None, status=500)
        ),
    )
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_yale_is_offline(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when yale is offline."""

    config_entry, socketio = await _create_yale_with_devices(
        hass, authenticate_side_effect=TimeoutError
    )

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_yale_late_auth_failure(hass: HomeAssistant) -> None:
    """Test we can detect a late auth failure."""
    config_entry, socketio = await _create_yale_with_devices(
        hass,
        authenticate_side_effect=InvalidAuth(
            "authfailed", ClientResponseError(None, None, status=401)
        ),
    )

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "pick_implementation"


async def test_unlock_throws_yale_api_http_error(hass: HomeAssistant) -> None:
    """Test unlock throws correct error on http error."""
    mocked_lock_detail = await _mock_operative_yale_lock_detail(hass)
    aiohttp_client_response_exception = ClientResponseError(None, None, status=400)

    def _unlock_return_activities_side_effect(access_token, device_id):
        raise YaleApiError(
            "This should bubble up as its user consumable",
            aiohttp_client_response_exception,
        )

    await _create_yale_with_devices(
        hass,
        [mocked_lock_detail],
        api_call_side_effects={
            "unlock_return_activities": _unlock_return_activities_side_effect
        },
    )
    data = {ATTR_ENTITY_ID: "lock.a6697750d607098bae8d6baa11ef8063_name"}
    with pytest.raises(
        HomeAssistantError,
        match=(
            "A6697750D607098BAE8D6BAA11EF8063 Name: This should bubble up as its user"
            " consumable"
        ),
    ):
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)


async def test_lock_throws_yale_api_http_error(hass: HomeAssistant) -> None:
    """Test lock throws correct error on http error."""
    mocked_lock_detail = await _mock_operative_yale_lock_detail(hass)
    aiohttp_client_response_exception = ClientResponseError(None, None, status=400)

    def _lock_return_activities_side_effect(access_token, device_id):
        raise YaleApiError(
            "This should bubble up as its user consumable",
            aiohttp_client_response_exception,
        )

    await _create_yale_with_devices(
        hass,
        [mocked_lock_detail],
        api_call_side_effects={
            "lock_return_activities": _lock_return_activities_side_effect
        },
    )
    data = {ATTR_ENTITY_ID: "lock.a6697750d607098bae8d6baa11ef8063_name"}
    with pytest.raises(
        HomeAssistantError,
        match=(
            "A6697750D607098BAE8D6BAA11EF8063 Name: This should bubble up as its user"
            " consumable"
        ),
    ):
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True)


async def test_open_throws_hass_service_not_supported_error(
    hass: HomeAssistant,
) -> None:
    """Test open throws correct error on entity does not support this service error."""
    mocked_lock_detail = await _mock_operative_yale_lock_detail(hass)
    await _create_yale_with_devices(hass, [mocked_lock_detail])
    data = {ATTR_ENTITY_ID: "lock.a6697750d607098bae8d6baa11ef8063_name"}
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_OPEN, data, blocking=True)


async def test_inoperative_locks_are_filtered_out(hass: HomeAssistant) -> None:
    """Ensure inoperative locks do not get setup."""
    yale_operative_lock = await _mock_operative_yale_lock_detail(hass)
    yale_inoperative_lock = await _mock_inoperative_yale_lock_detail(hass)
    await _create_yale_with_devices(hass, [yale_operative_lock, yale_inoperative_lock])

    lock_abc_name = hass.states.get("lock.abc_name")
    assert lock_abc_name is None
    lock_a6697750d607098bae8d6baa11ef8063_name = hass.states.get(
        "lock.a6697750d607098bae8d6baa11ef8063_name"
    )
    assert lock_a6697750d607098bae8d6baa11ef8063_name.state == LockState.LOCKED


async def test_lock_has_doorsense(hass: HomeAssistant) -> None:
    """Check to see if a lock has doorsense."""
    doorsenselock = await _mock_doorsense_enabled_yale_lock_detail(hass)
    nodoorsenselock = await _mock_doorsense_missing_yale_lock_detail(hass)
    await _create_yale_with_devices(hass, [doorsenselock, nodoorsenselock])

    binary_sensor_online_with_doorsense_name_open = hass.states.get(
        "binary_sensor.online_with_doorsense_name_door"
    )
    assert binary_sensor_online_with_doorsense_name_open.state == STATE_ON
    binary_sensor_missing_doorsense_id_name_open = hass.states.get(
        "binary_sensor.missing_with_doorsense_name_door"
    )
    assert binary_sensor_missing_doorsense_id_name_open is None


async def test_load_unload(hass: HomeAssistant) -> None:
    """Config entry can be unloaded."""

    yale_operative_lock = await _mock_operative_yale_lock_detail(hass)
    yale_inoperative_lock = await _mock_inoperative_yale_lock_detail(hass)
    config_entry, socketio = await _create_yale_with_devices(
        hass, [yale_operative_lock, yale_inoperative_lock]
    )

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_triggers_ble_discovery(
    hass: HomeAssistant, mock_discovery: Mock
) -> None:
    """Test that loading a lock that supports offline ble operation passes the keys to yalexe_ble."""

    yale_lock_with_key = await _mock_lock_with_offline_key(hass)
    yale_lock_without_key = await _mock_operative_yale_lock_detail(hass)

    config_entry, socketio = await _create_yale_with_devices(
        hass, [yale_lock_with_key, yale_lock_without_key]
    )
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert len(mock_discovery.mock_calls) == 1
    assert mock_discovery.mock_calls[0].kwargs["data"] == {
        "name": "Front Door Lock",
        "address": None,
        "serial": "X2FSW05DGA",
        "key": "kkk01d4300c1dcxxx1c330f794941111",
        "slot": 1,
    }


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    yale_operative_lock = await _mock_operative_yale_lock_detail(hass)
    config_entry, socketio = await _create_yale_with_devices(
        hass, [yale_operative_lock]
    )
    entity = entity_registry.entities["lock.a6697750d607098bae8d6baa11ef8063_name"]

    device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, config_entry.entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    response = await client.remove_device(dead_device_entry.id, config_entry.entry_id)
    assert response["success"]
