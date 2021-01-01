"""The tests for the august platform."""
import asyncio
from unittest.mock import patch

from aiohttp import ClientResponseError
from august.authenticator_common import AuthenticationState
from august.exceptions import AugustApiAIOHTTPError

from homeassistant import setup
from homeassistant.components.august.const import (
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DEFAULT_AUGUST_CONFIG_FILE,
    DOMAIN,
)
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_ON,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.august.mocks import (
    _create_august_with_devices,
    _mock_august_authentication,
    _mock_doorsense_enabled_august_lock_detail,
    _mock_doorsense_missing_august_lock_detail,
    _mock_get_config,
    _mock_inoperative_august_lock_detail,
    _mock_operative_august_lock_detail,
)


async def test_august_is_offline(hass):
    """Config entry state is ENTRY_STATE_SETUP_RETRY when august is offline."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "august.authenticator_async.AuthenticatorAsync.async_authenticate",
        side_effect=asyncio.TimeoutError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unlock_throws_august_api_http_error(hass):
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
    assert (
        str(last_err)
        == "A6697750D607098BAE8D6BAA11EF8063 Name: This should bubble up as its user consumable"
    )


async def test_lock_throws_august_api_http_error(hass):
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
    assert (
        str(last_err)
        == "A6697750D607098BAE8D6BAA11EF8063 Name: This should bubble up as its user consumable"
    )


async def test_inoperative_locks_are_filtered_out(hass):
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


async def test_lock_has_doorsense(hass):
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


async def test_set_up_from_yaml(hass):
    """Test to make sure config is imported from yaml."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.august.async_setup_august",
        return_value=True,
    ) as mock_setup_august, patch(
        "homeassistant.components.august.config_flow.AugustGateway.async_authenticate",
        return_value=True,
    ):
        assert await async_setup_component(hass, DOMAIN, _mock_get_config())
    await hass.async_block_till_done()
    assert len(mock_setup_august.mock_calls) == 1
    call = mock_setup_august.call_args
    args, _ = call
    imported_config_entry = args[1]
    # The import must use DEFAULT_AUGUST_CONFIG_FILE so they
    # do not loose their token when config is migrated
    assert imported_config_entry.data == {
        CONF_ACCESS_TOKEN_CACHE_FILE: DEFAULT_AUGUST_CONFIG_FILE,
        CONF_INSTALL_ID: None,
        CONF_LOGIN_METHOD: "email",
        CONF_PASSWORD: "mocked_password",
        CONF_TIMEOUT: None,
        CONF_USERNAME: "mocked_username",
    }


async def test_auth_fails(hass):
    """Config entry state is ENTRY_STATE_SETUP_ERROR when auth fails."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "august.authenticator_async.AuthenticatorAsync.async_authenticate",
        side_effect=ClientResponseError(None, None, status=401),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "user"


async def test_bad_password(hass):
    """Config entry state is ENTRY_STATE_SETUP_ERROR when the password has been changed."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "august.authenticator_async.AuthenticatorAsync.async_authenticate",
        return_value=_mock_august_authentication(
            "original_token", 1234, AuthenticationState.BAD_PASSWORD
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "user"


async def test_http_failure(hass):
    """Config entry state is ENTRY_STATE_SETUP_RETRY when august is offline."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "august.authenticator_async.AuthenticatorAsync.async_authenticate",
        side_effect=ClientResponseError(None, None, status=500),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_SETUP_RETRY

    assert hass.config_entries.flow.async_progress() == []


async def test_unknown_auth_state(hass):
    """Config entry state is ENTRY_STATE_SETUP_ERROR when august is in an unknown auth state."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "august.authenticator_async.AuthenticatorAsync.async_authenticate",
        return_value=_mock_august_authentication("original_token", 1234, None),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()

    assert flows[0]["step_id"] == "user"


async def test_requires_validation_state(hass):
    """Config entry state is ENTRY_STATE_SETUP_ERROR when august requires validation."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_mock_get_config()[DOMAIN],
        title="August august",
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.flow.async_progress() == []

    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "august.authenticator_async.AuthenticatorAsync.async_authenticate",
        return_value=_mock_august_authentication(
            "original_token", 1234, AuthenticationState.REQUIRES_VALIDATION
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_SETUP_ERROR

    assert hass.config_entries.flow.async_progress() == []
