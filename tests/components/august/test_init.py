"""The tests for the august platform."""
import asyncio
from unittest.mock import patch

from aiohttp import ClientResponseError
from yalexs.authenticator_common import AuthenticationState
from yalexs.exceptions import AugustApiAIOHTTPError

from homeassistant.components.august.const import DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component

from .mocks import (
    _create_august_with_devices,
    _mock_august_authentication,
    _mock_doorsense_enabled_august_lock_detail,
    _mock_doorsense_missing_august_lock_detail,
    _mock_get_config,
    _mock_inoperative_august_lock_detail,
    _mock_lock_with_offline_key,
    _mock_operative_august_lock_detail,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_august_api_is_failing(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when august api is failing."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        side_effect=ClientResponseError(None, None, status=500),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_august_is_offline(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when august is offline."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        side_effect=asyncio.TimeoutError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unlock_throws_august_api_http_error(hass: HomeAssistant) -> None:
    """Test unlock throws correct error on http error."""
    mocked_lock_detail = await _mock_operative_august_lock_detail(hass)

    def _unlock_return_activities_side_effect(access_token, device_id):
        raise AugustApiAIOHTTPError("This should bubble up as its user consumable")

    await _create_august_with_devices(
        hass,
        [mocked_lock_detail],
        api_call_side_effects={
            "unlock_return_activities": _unlock_return_activities_side_effect
        },
    )
    last_err = None
    data = {ATTR_ENTITY_ID: "lock.a6697750d607098bae8d6baa11ef8063_name"}
    try:
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)
    except HomeAssistantError as err:
        last_err = err
    assert str(last_err) == (
        "A6697750D607098BAE8D6BAA11EF8063 Name: This should bubble up as its user"
        " consumable"
    )


async def test_lock_throws_august_api_http_error(hass: HomeAssistant) -> None:
    """Test lock throws correct error on http error."""
    mocked_lock_detail = await _mock_operative_august_lock_detail(hass)

    def _lock_return_activities_side_effect(access_token, device_id):
        raise AugustApiAIOHTTPError("This should bubble up as its user consumable")

    await _create_august_with_devices(
        hass,
        [mocked_lock_detail],
        api_call_side_effects={
            "lock_return_activities": _lock_return_activities_side_effect
        },
    )
    last_err = None
    data = {ATTR_ENTITY_ID: "lock.a6697750d607098bae8d6baa11ef8063_name"}
    try:
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True)
    except HomeAssistantError as err:
        last_err = err
    assert str(last_err) == (
        "A6697750D607098BAE8D6BAA11EF8063 Name: This should bubble up as its user"
        " consumable"
    )


async def test_inoperative_locks_are_filtered_out(hass: HomeAssistant) -> None:
    """Ensure inoperative locks do not get setup."""
    august_operative_lock = await _mock_operative_august_lock_detail(hass)
    august_inoperative_lock = await _mock_inoperative_august_lock_detail(hass)
    await _create_august_with_devices(
        hass, [august_operative_lock, august_inoperative_lock]
    )

    lock_abc_name = hass.states.get("lock.abc_name")
    assert lock_abc_name is None
    lock_a6697750d607098bae8d6baa11ef8063_name = hass.states.get(
        "lock.a6697750d607098bae8d6baa11ef8063_name"
    )
    assert lock_a6697750d607098bae8d6baa11ef8063_name.state == STATE_LOCKED


async def test_lock_has_doorsense(hass: HomeAssistant) -> None:
    """Check to see if a lock has doorsense."""
    doorsenselock = await _mock_doorsense_enabled_august_lock_detail(hass)
    nodoorsenselock = await _mock_doorsense_missing_august_lock_detail(hass)
    await _create_august_with_devices(hass, [doorsenselock, nodoorsenselock])

    binary_sensor_online_with_doorsense_name_open = hass.states.get(
        "binary_sensor.online_with_doorsense_name_open"
    )
    assert binary_sensor_online_with_doorsense_name_open.state == STATE_ON
    binary_sensor_missing_doorsense_id_name_open = hass.states.get(
        "binary_sensor.missing_doorsense_id_name_open"
    )
    assert binary_sensor_missing_doorsense_id_name_open is None


async def test_auth_fails(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_ERROR when auth fails."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        side_effect=ClientResponseError(None, None, status=401),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "reauth_validate"


async def test_bad_password(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_ERROR when the password has been changed."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        return_value=_mock_august_authentication(
            "original_token", 1234, AuthenticationState.BAD_PASSWORD
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "reauth_validate"


async def test_http_failure(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when august is offline."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        side_effect=ClientResponseError(None, None, status=500),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    assert hass.config_entries.flow.async_progress() == []


async def test_unknown_auth_state(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_ERROR when august is in an unknown auth state."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        return_value=_mock_august_authentication("original_token", 1234, None),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "reauth_validate"


async def test_requires_validation_state(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_ERROR when august requires validation."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        return_value=_mock_august_authentication(
            "original_token", 1234, AuthenticationState.REQUIRES_VALIDATION
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    assert len(hass.config_entries.flow.async_progress()) == 1
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == "reauth"


async def test_unknown_auth_http_401(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_ERROR when august gets an http."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    with patch(
        "yalexs.authenticator_async.AuthenticatorAsync.async_authenticate",
        return_value=_mock_august_authentication("original_token", 1234, None),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "reauth_validate"


async def test_load_unload(hass: HomeAssistant) -> None:
    """Config entry can be unloaded."""

    august_operative_lock = await _mock_operative_august_lock_detail(hass)
    august_inoperative_lock = await _mock_inoperative_august_lock_detail(hass)
    config_entry = await _create_august_with_devices(
        hass, [august_operative_lock, august_inoperative_lock]
    )

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_load_triggers_ble_discovery(hass: HomeAssistant) -> None:
    """Test that loading a lock that supports offline ble operation passes the keys to yalexe_ble."""

    august_lock_with_key = await _mock_lock_with_offline_key(hass)
    august_lock_without_key = await _mock_operative_august_lock_detail(hass)

    with patch(
        "homeassistant.components.august.discovery_flow.async_create_flow"
    ) as mock_discovery:
        config_entry = await _create_august_with_devices(
            hass, [august_lock_with_key, august_lock_without_key]
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


async def remove_device(ws_client, device_id, config_entry_id):
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


async def test_device_remove_devices(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    august_operative_lock = await _mock_operative_august_lock_detail(hass)
    config_entry = await _create_august_with_devices(hass, [august_operative_lock])
    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["lock.a6697750d607098bae8d6baa11ef8063_name"]

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(
            await hass_ws_client(hass), device_entry.id, config_entry.entry_id
        )
        is False
    )

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    assert (
        await remove_device(
            await hass_ws_client(hass), dead_device_entry.id, config_entry.entry_id
        )
        is True
    )
