"""Test the Mammotion config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.mammotion.const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNTNAME,
    CONF_BLE_DEVICES,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_IGNORE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from . import (
    ACCOUNT_ID,
    ACCOUNT_NAME,
    DEFAULT_ADDRESS,
    DEFAULT_MAC,
    DEFAULT_NAME,
    LOGIN_INFO,
    LUBA_SERVICE_INFO,
    OTHER_LOGIN_INFO,
    service_info,
)

USER_INPUT = {CONF_ACCOUNTNAME: ACCOUNT_NAME, CONF_PASSWORD: "password"}

LOGIN_ERRORS = [
    pytest.param({"login_info": None}, "invalid_auth", id="invalid_auth"),
    pytest.param(
        {"login_v2.side_effect": ClientConnectionError("Conn Err")},
        "cannot_connect",
        id="cannot_connect",
    ),
    pytest.param(
        {"login_v2.side_effect": RuntimeError("boom")}, "unknown", id="unknown"
    ),
]


def _login_succeeds(mock_mammotion_http: MagicMock) -> None:
    """Make the next login succeed."""
    mock_mammotion_http.configure_mock(
        **{"login_info": LOGIN_INFO, "login_v2.side_effect": None}
    )


def _add_owned_mower(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
    connections: set[tuple[str, str]],
) -> dr.DeviceEntry:
    """Register the default mower as a device of the entry."""
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEFAULT_NAME)},
        connections=connections,
    )


@pytest.mark.usefixtures("mock_mammotion_http")
async def test_bluetooth_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a discovered mower is set up with its Bluetooth address."""
    inject_bluetooth_service_info(hass, LUBA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["step_id"] == "bluetooth_confirm"
    assert result["context"]["title_placeholders"] == {"name": DEFAULT_NAME}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_NAME
    assert result["result"].unique_id == ACCOUNT_ID
    assert result["data"] == {
        CONF_ACCOUNTNAME: ACCOUNT_NAME,
        CONF_PASSWORD: "password",
        CONF_ACCOUNT_ID: ACCOUNT_ID,
        CONF_BLE_DEVICES: {DEFAULT_NAME: DEFAULT_MAC},
    }
    mock_setup_entry.assert_called_once()


async def test_bluetooth_discovery_ignored(hass: HomeAssistant) -> None:
    """Test discovery aborts for a mower the user ignored."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id=DEFAULT_MAC
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LUBA_SERVICE_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_not_supported(hass: HomeAssistant) -> None:
    """Test discovery aborts for a device that is not a supported mower."""
    other = service_info("RTK-ABC123", "11:22:33:44:55:66")
    inject_bluetooth_service_info(hass, other)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=async_last_service_info(hass, other.address),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_no_longer_present(hass: HomeAssistant) -> None:
    """Test discovery aborts when the mower is no longer advertising."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LUBA_SERVICE_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_longer_present"


@pytest.mark.usefixtures("mock_mammotion_http")
async def test_bluetooth_discovery_skips_ignored_entries(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test an ignored entry for another mower does not claim this one."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id="11:22:33:44:55:66"
    ).add_to_hass(hass)

    inject_bluetooth_service_info(hass, LUBA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID
    assert result["data"][CONF_BLE_DEVICES] == {DEFAULT_NAME: DEFAULT_MAC}
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("stored_connections", "stored_ble_devices", "expected_logins"),
    [
        pytest.param(set(), {}, 2, id="new_address_reloads_once"),
        pytest.param(
            {(dr.CONNECTION_BLUETOOTH, DEFAULT_MAC)},
            {},
            1,
            id="known_address_missing_from_entry_data",
        ),
        pytest.param(
            {(dr.CONNECTION_BLUETOOTH, DEFAULT_MAC)},
            {DEFAULT_NAME: DEFAULT_MAC},
            1,
            id="known_address_already_in_entry_data",
        ),
    ],
)
async def test_bluetooth_discovery_of_owned_mower(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mammotion: MagicMock,
    stored_connections: set[tuple[str, str]],
    stored_ble_devices: dict[str, str],
    expected_logins: int,
) -> None:
    """Test discovering a configured mower records its address on the entry.

    A reload stands up a second client alongside the running one, and the two
    MQTT sessions share a client_id, so the broker rejects both. Only an address
    the device registry did not know yet may reload the entry.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_BLE_DEVICES: stored_ble_devices},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEFAULT_NAME), mock_config_entry.entry_id
    )
    assert device is not None
    device_registry.async_update_device(device.id, new_connections=stored_connections)

    inject_bluetooth_service_info(hass, LUBA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_BLE_DEVICES] == {DEFAULT_NAME: DEFAULT_MAC}
    device = device_registry.async_get(device.id)
    assert device is not None
    assert (dr.CONNECTION_BLUETOOTH, DEFAULT_MAC) in device.connections
    assert mock_mammotion.login_and_initiate_cloud.await_count == expected_logins


async def test_bluetooth_discovery_of_mower_owned_by_unloaded_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discovery records the address of an entry that is not loaded."""
    mock_config_entry.add_to_hass(hass)
    device = _add_owned_mower(hass, device_registry, mock_config_entry, set())

    inject_bluetooth_service_info(hass, LUBA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_config_entry.data[CONF_BLE_DEVICES] == {DEFAULT_NAME: DEFAULT_MAC}
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.connections == {(dr.CONNECTION_BLUETOOTH, DEFAULT_MAC)}


@pytest.mark.parametrize(
    "stored_ble_devices",
    [
        pytest.param({}, id="no_stored_address"),
        pytest.param({DEFAULT_NAME: "11:22:33:44:55:66"}, id="stale_stored_address"),
    ],
)
async def test_bluetooth_confirm_mower_configured_meanwhile(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    stored_ble_devices: dict[str, str],
) -> None:
    """Test confirming a mower another flow configured meanwhile aborts.

    The discovered address replaces one the entry stored for the same mower.
    """
    inject_bluetooth_service_info(hass, LUBA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["step_id"] == "bluetooth_confirm"

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_BLE_DEVICES: stored_ble_devices},
    )
    _add_owned_mower(
        hass,
        device_registry,
        mock_config_entry,
        {(dr.CONNECTION_BLUETOOTH, DEFAULT_MAC)},
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_BLE_DEVICES] == {DEFAULT_NAME: DEFAULT_MAC}


@pytest.mark.parametrize(
    ("user_input", "expected_ble_devices"),
    [
        pytest.param(
            {CONF_ADDRESS: DEFAULT_ADDRESS},
            {CONF_BLE_DEVICES: {DEFAULT_NAME: DEFAULT_MAC}},
            id="pick",
        ),
        pytest.param({}, {}, id="skip"),
    ],
)
@pytest.mark.usefixtures("mock_mammotion_http")
async def test_user_step_discovered_mower(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    user_input: dict[str, str],
    expected_ble_devices: dict[str, Any],
) -> None:
    """Test picking or skipping a discovered mower before logging in."""
    inject_bluetooth_service_info(hass, LUBA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID
    assert result["data"] == {
        CONF_ACCOUNTNAME: ACCOUNT_NAME,
        CONF_PASSWORD: "password",
        CONF_ACCOUNT_ID: ACCOUNT_ID,
        **expected_ble_devices,
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_offers_only_new_mowers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
) -> None:
    """Test the picker leaves out ignored, owned and unsupported devices."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id="11:22:33:44:55:66"
    ).add_to_hass(hass)
    mock_config_entry.add_to_hass(hass)
    _add_owned_mower(
        hass,
        device_registry,
        mock_config_entry,
        {(dr.CONNECTION_BLUETOOTH, DEFAULT_MAC)},
    )
    for info in (
        service_info("Luba-IGNORED", "11:22:33:44:55:66"),
        LUBA_SERVICE_INFO,
        service_info("RTK-XYZ789", "22:33:44:55:66:77"),
        service_info("Yuka-NEW", "99:88:77:66:55:44"),
    ):
        inject_bluetooth_service_info(hass, info)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_ADDRESS].container == {
        "99:88:77:66:55:44": "Yuka-NEW"
    }

    mock_mammotion_http.login_info = OTHER_LOGIN_INFO
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "99:88:77:66:55:44"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNTNAME: "other@example.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "other_user"
    assert result["data"][CONF_BLE_DEVICES] == {"Yuka-NEW": "99:88:77:66:55:44"}
    assert result["result"].state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_mammotion_http")
async def test_user_step_no_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the user step goes straight to the login without discovered mowers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID
    assert CONF_BLE_DEVICES not in result["data"]
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    "account",
    [
        pytest.param("User@Example.com", id="account_name"),
        pytest.param(ACCOUNT_ID, id="account_id"),
    ],
)
async def test_wifi_step_account_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
    account: str,
) -> None:
    """Test a configured account aborts before logging in.

    The login would supersede the cloud session the configured entry uses.
    """
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCOUNTNAME: account, CONF_PASSWORD: "password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_mammotion_http.login_v2.assert_not_awaited()


async def test_wifi_step_alias_of_configured_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
) -> None:
    """Test a login name that resolves to a configured account aborts."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCOUNTNAME: "+64211234567", CONF_PASSWORD: "pw"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_mammotion_http.login_v2.assert_awaited_once_with("+64211234567", "pw")


@pytest.mark.usefixtures("mock_mammotion_http")
async def test_user_step_skips_ignored_mower(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a mower whose discovery was ignored is not offered again."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id=DEFAULT_MAC
    ).add_to_hass(hass)
    inject_bluetooth_service_info(hass, LUBA_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID
    assert CONF_BLE_DEVICES not in result["data"]
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(("failure", "expected_error"), LOGIN_ERRORS)
async def test_wifi_step_errors(
    hass: HomeAssistant,
    mock_mammotion_http: MagicMock,
    mock_setup_entry: AsyncMock,
    failure: dict[str, Any],
    expected_error: str,
) -> None:
    """Test the login step shows an error and recovers once the login works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_mammotion_http.configure_mock(**failure)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi"
    assert result["errors"] == {"base": expected_error}

    _login_succeeds(mock_mammotion_http)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_ID
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    "account",
    [
        pytest.param("new@example.com", id="new_account_name"),
        pytest.param(ACCOUNT_NAME, id="same_account_name"),
    ],
)
@pytest.mark.usefixtures("mock_mammotion_http")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    account: str,
) -> None:
    """Test reconfiguring the account updates the entry and reloads it."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    schema = result["data_schema"]
    assert get_schema_suggested_value(schema.schema, CONF_ACCOUNTNAME) == ACCOUNT_NAME
    # The stored password must not be sent to the browser as a default.
    with pytest.raises(probatio.Invalid):
        schema({CONF_ACCOUNTNAME: ACCOUNT_NAME})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNTNAME: account, CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_ACCOUNTNAME: account,
        CONF_PASSWORD: "new_password",
        CONF_ACCOUNT_ID: ACCOUNT_ID,
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(("failure", "expected_error"), LOGIN_ERRORS)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
    mock_setup_entry: AsyncMock,
    failure: dict[str, Any],
    expected_error: str,
) -> None:
    """Test reconfiguration shows an error and recovers once the login works."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    mock_mammotion_http.configure_mock(**failure)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNTNAME: "new@example.com", CONF_PASSWORD: "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}
    assert mock_config_entry.data[CONF_ACCOUNTNAME] == ACCOUNT_NAME

    _login_succeeds(mock_mammotion_http)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNTNAME: "new@example.com", CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_ACCOUNTNAME] == "new@example.com"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_account_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
) -> None:
    """Test reconfiguration aborts when the login is a different account."""
    mock_config_entry.add_to_hass(hass)
    mock_mammotion_http.login_info = OTHER_LOGIN_INFO

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNTNAME: "other@example.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_ACCOUNTNAME] == ACCOUNT_NAME


async def test_reconfigure_flow_account_of_other_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
) -> None:
    """Test reconfiguring to another entry's account aborts before logging in.

    The login would supersede the cloud session the other entry uses.
    """
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        title="other@example.com",
        data={
            CONF_ACCOUNTNAME: "other@example.com",
            CONF_PASSWORD: "password",
            CONF_ACCOUNT_ID: "other_user",
        },
        unique_id="other_user",
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNTNAME: "Other@Example.com", CONF_PASSWORD: "password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_mammotion_http.login_v2.assert_not_awaited()
    assert mock_config_entry.data[CONF_ACCOUNTNAME] == ACCOUNT_NAME


@pytest.mark.usefixtures("mock_mammotion_http")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth updates the password and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["account_name"] == ACCOUNT_NAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(("failure", "expected_error"), LOGIN_ERRORS)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
    mock_setup_entry: AsyncMock,
    failure: dict[str, Any],
    expected_error: str,
) -> None:
    """Test reauth shows an error and recovers once the login works."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    mock_mammotion_http.configure_mock(**failure)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    _login_succeeds(mock_mammotion_http)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mammotion_http: MagicMock,
) -> None:
    """Test reauth aborts when the password belongs to another account."""
    mock_config_entry.add_to_hass(hass)
    mock_mammotion_http.login_info = OTHER_LOGIN_INFO

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_PASSWORD] == "password"
