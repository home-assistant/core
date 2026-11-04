"""Test the Seafile config flow."""

import asyncio
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock

from aioseafile import (
    SeafileAuthenticationError,
    SeafileConnectionError,
    SeafileTwoFactorRequiredError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.seafile.const import (
    CONF_BACKUP,
    CONF_BACKUP_PATH,
    CONF_LIBRARIES,
    CONF_LIBRARY_ID,
    DOMAIN,
    SUBENTRY_TYPE_LIBRARY,
)
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

from . import setup_integration
from .conftest import (
    ACCOUNT_EMAIL,
    ENCRYPTED_LIBRARY_ID,
    LIBRARY_ID,
    SUBENTRY_ID,
    TOKEN,
    URL,
)

NEW_LIBRARY_ID = "0c8bd7d5-6ba2-4e7d-9a8b-1f2f4c6ad2b1"

USER_INPUT = {
    CONF_URL: URL,
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "hunter2",
    CONF_VERIFY_SSL: True,
}


async def _start_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_seafile_client: AsyncMock) -> None:
    """Test logging in and picking libraries creates the entry and its subentries."""
    flow_id = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "libraries"
    # Encrypted libraries can't be picked.
    options = result["data_schema"].schema[CONF_LIBRARIES].config["options"]
    assert [option["value"] for option in options] == [LIBRARY_ID]

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_LIBRARIES: [LIBRARY_ID]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com (seafile.example.com)"
    assert result["data"] == {CONF_URL: URL, CONF_TOKEN: TOKEN, CONF_VERIFY_SSL: True}
    assert result["result"].unique_id == ACCOUNT_EMAIL
    assert result["subentries"] == [
        ConfigSubentryData(
            data={
                CONF_LIBRARY_ID: LIBRARY_ID,
                CONF_BACKUP: False,
                CONF_BACKUP_PATH: "/Home Assistant backups",
            },
            subentry_type=SUBENTRY_TYPE_LIBRARY,
            title="Documents",
            unique_id=LIBRARY_ID,
        )
    ]
    # The password is only used to create a token registered as a device.
    kwargs = mock_seafile_client.get_auth_token.call_args.kwargs
    assert len(kwargs["device_id"]) == 40
    assert kwargs["device_name"] == f"Home Assistant ({hass.config.location_name})"
    mock_seafile_client.logout_device.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_without_libraries(
    hass: HomeAssistant, mock_seafile_client: AsyncMock
) -> None:
    """Test the entry can be created without picking a library."""
    flow_id = await _start_flow(hass)
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_EMAIL
    assert result["subentries"] == ()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_two_factor_authentication(
    hass: HomeAssistant, mock_seafile_client: AsyncMock
) -> None:
    """Test the code is asked when the account uses two-factor authentication."""
    mock_seafile_client.get_auth_token.side_effect = [
        SeafileTwoFactorRequiredError,
        SeafileTwoFactorRequiredError,
        TOKEN,
    ]
    flow_id = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"

    result = await hass.config_entries.flow.async_configure(flow_id, {"otp": "000000"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {"base": "invalid_otp"}

    result = await hass.config_entries.flow.async_configure(flow_id, {"otp": "123456"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "libraries"
    assert mock_seafile_client.get_auth_token.call_args.args[2] == "123456"

    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_EMAIL


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(SeafileAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(SeafileConnectionError, "cannot_connect", id="cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_two_factor_errors(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test errors after entering the code are shown on the code step."""
    mock_seafile_client.get_auth_token.side_effect = [
        SeafileTwoFactorRequiredError,
        exception,
        TOKEN,
    ]
    flow_id = await _start_flow(hass)
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    result = await hass.config_entries.flow.async_configure(flow_id, {"otp": "123456"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(flow_id, {"otp": "123456"})
    assert result["step_id"] == "libraries"
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_EMAIL


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(SeafileAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(SeafileConnectionError, "cannot_connect", id="cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_login_errors(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test login errors are shown and the flow can recover."""
    mock_seafile_client.get_auth_token.side_effect = exception
    flow_id = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_seafile_client.get_auth_token.side_effect = None
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["step_id"] == "libraries"
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_EMAIL


@pytest.mark.usefixtures("mock_setup_entry")
async def test_token_revoked_after_connection_error(
    hass: HomeAssistant, mock_seafile_client: AsyncMock
) -> None:
    """Test a token created before a connection error is revoked."""
    mock_seafile_client.get_libraries.side_effect = SeafileConnectionError
    flow_id = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_seafile_client.logout_device.assert_awaited_once()

    mock_seafile_client.get_libraries.side_effect = None
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_EMAIL
    assert result["data"][CONF_TOKEN] == TOKEN


@pytest.mark.usefixtures("mock_setup_entry")
async def test_token_revoked_when_flow_cancelled(
    hass: HomeAssistant, mock_seafile_client: AsyncMock
) -> None:
    """Test the token is revoked when the flow is cancelled at the libraries step."""
    flow_id = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["step_id"] == "libraries"

    hass.config_entries.flow.async_abort(flow_id)
    await hass.async_block_till_done()
    mock_seafile_client.logout_device.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_token_revoked_when_flow_cancelled_during_login(
    hass: HomeAssistant, mock_seafile_client: AsyncMock
) -> None:
    """Test a token that arrives after the flow was cancelled is revoked."""
    login_started = asyncio.Event()
    release_login = asyncio.Event()

    async def _get_auth_token(*args: Any, **kwargs: Any) -> str:
        login_started.set()
        await release_login.wait()
        return TOKEN

    mock_seafile_client.get_auth_token.side_effect = _get_auth_token
    flow_id = await _start_flow(hass)
    configure = hass.async_create_task(
        hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    )
    await login_started.wait()

    hass.config_entries.flow.async_abort(flow_id)
    release_login.set()
    # The flow manager rejects the late result of the removed flow.
    with pytest.raises(UnknownFlow):
        await configure
    await hass.async_block_till_done()

    mock_seafile_client.logout_device.assert_awaited_once()
    mock_seafile_client.get_account_info.assert_not_awaited()


@pytest.mark.parametrize(
    "logout_error",
    [
        pytest.param(None, id="logged_out"),
        pytest.param(SeafileConnectionError, id="logout_failed"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    logout_error: type[Exception] | None,
) -> None:
    """Test the same account can't be added twice and its new token is revoked."""
    mock_seafile_client.logout_device.side_effect = logout_error
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_seafile_client.logout_device.assert_awaited_once()


async def test_add_library(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a library, including one created after setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=mock_config_entry.title,
        data=mock_config_entry.data,
        unique_id=mock_config_entry.unique_id,
    )
    await setup_integration(hass, entry)
    new_library = replace(
        mock_seafile_client.get_libraries.return_value[0],
        id=NEW_LIBRARY_ID,
        name="Photos",
    )
    mock_seafile_client.get_libraries.return_value = [
        *mock_seafile_client.get_libraries.return_value,
        new_library,
    ]

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_LIBRARY),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema[CONF_LIBRARY_ID].config["options"]
    assert [option["value"] for option in options] == [LIBRARY_ID, NEW_LIBRARY_ID]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LIBRARY_ID: LIBRARY_ID, CONF_BACKUP: True, CONF_BACKUP_PATH: "HA/"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Documents"
    assert result["unique_id"] == LIBRARY_ID
    # The folder is stored as an absolute path.
    assert result["data"] == {
        CONF_LIBRARY_ID: LIBRARY_ID,
        CONF_BACKUP: True,
        CONF_BACKUP_PATH: "/HA",
    }
    assert hass.states.get("sensor.documents_size") is not None


async def test_add_library_cannot_connect(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a library aborts when the libraries can't be fetched."""
    await setup_integration(hass, mock_config_entry)
    mock_seafile_client.get_libraries.side_effect = SeafileConnectionError

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_LIBRARY),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_in_progress(
    hass: HomeAssistant, mock_seafile_client: AsyncMock
) -> None:
    """Test a second flow for the same account aborts and revokes its token."""
    first_flow_id = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(first_flow_id, USER_INPUT)
    assert result["step_id"] == "libraries"

    second_flow_id = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(second_flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    mock_seafile_client.logout_device.assert_awaited_once()


@pytest.mark.usefixtures("mock_seafile_client")
async def test_add_library_none_left(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a library aborts when all unencrypted libraries are added."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_LIBRARY),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_libraries"
    assert ENCRYPTED_LIBRARY_ID not in {
        subentry.unique_id for subentry in mock_config_entry.subentries.values()
    }


async def test_add_library_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a library needs a loaded entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_LIBRARY),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.usefixtures("mock_seafile_client")
async def test_reconfigure_library(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning backups off and changing the folder of a library."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_subentry_reconfigure_flow(hass, SUBENTRY_ID)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_BACKUP: False, CONF_BACKUP_PATH: "/Backups/HA/"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.subentries[SUBENTRY_ID].data == {
        CONF_LIBRARY_ID: LIBRARY_ID,
        CONF_BACKUP: False,
        CONF_BACKUP_PATH: "/Backups/HA",
    }
