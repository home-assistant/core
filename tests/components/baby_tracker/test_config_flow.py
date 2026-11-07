"""Tests for the config flow's user step."""

from collections.abc import Callable
from unittest.mock import AsyncMock
import uuid

from pybabytracker import AuthenticationError, BabyTrackerConnectionError, ProtocolError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.baby_tracker.const import CONF_DEVICE_UUID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import EMAIL, PASSWORD
from .fake_server import FakeServer


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def _submit(
    hass: HomeAssistant, flow_id: str, email: str = EMAIL, password: str = PASSWORD
):
    return await hass.config_entries.flow.async_configure(
        flow_id, {CONF_EMAIL: email, CONF_PASSWORD: password}
    )


async def test_shows_the_email_and_password_form(hass: HomeAssistant) -> None:
    """Test the user step asks for an email and a password."""
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert set(result["data_schema"].schema) == {CONF_EMAIL, CONF_PASSWORD}


async def test_full_flow_creates_one_entry(
    hass: HomeAssistant, server: FakeServer, mock_setup_entry: AsyncMock
) -> None:
    """Test a working login creates one entry for the account."""
    result = await _start(hass)
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"][CONF_EMAIL] == EMAIL
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["result"].unique_id == EMAIL
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    # The entry keeps the device ID the login check signed in with, and that client is closed.
    device_uuid = result["data"][CONF_DEVICE_UUID]
    assert str(uuid.UUID(device_uuid)).upper() == device_uuid.upper()
    assert server.sign_ins[0]["device_uuid"] == device_uuid
    assert server.sign_ins[0]["device_name"] == "Home Assistant"
    assert server.clients[0].closed


@pytest.mark.parametrize(
    ("break_login", "error"),
    [
        (lambda server: setattr(server, "password", "test-other"), "invalid_auth"),
        (
            lambda server: setattr(
                server, "sign_in_error", AuthenticationError("rejected")
            ),
            "invalid_auth",
        ),
        (
            lambda server: setattr(
                server, "sign_in_error", BabyTrackerConnectionError("down")
            ),
            "cannot_connect",
        ),
        (
            lambda server: setattr(server, "sign_in_error", ProtocolError("odd")),
            "unknown",
        ),
        (
            lambda server: setattr(server, "sign_in_error", RuntimeError("surprise")),
            "unknown",
        ),
    ],
    ids=[
        "wrong-password",
        "auth-error",
        "cannot-connect",
        "protocol-error",
        "unexpected-error",
    ],
)
async def test_form_errors_show_on_the_form_and_the_flow_recovers(
    hass: HomeAssistant,
    server: FakeServer,
    mock_setup_entry: AsyncMock,
    break_login: Callable[[FakeServer], None],
    error: str,
) -> None:
    """Test a failed login shows an error, and the same form then finishes."""
    break_login(server)
    result = await _start(hass)
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert not mock_setup_entry.mock_calls
    assert all(client.closed for client in server.clients)

    # The login works again: the same form finishes, so the flow is able to recover.
    server.password = PASSWORD
    server.sign_in_error = None
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"][CONF_EMAIL] == EMAIL
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["result"].unique_id == EMAIL
    assert len(mock_setup_entry.mock_calls) == 1


async def test_the_form_keeps_what_was_typed_after_an_error(
    hass: HomeAssistant, server: FakeServer
) -> None:
    """Test the form keeps the email after an error."""
    result = await _start(hass)
    result = await _submit(hass, result["flow_id"], password="test-wrong")

    suggested = {str(key): key.description for key in result["data_schema"].schema}
    assert suggested[CONF_EMAIL] == {"suggested_value": EMAIL}


@pytest.mark.parametrize(
    "email", [EMAIL, EMAIL.upper()], ids=["same", "different-case"]
)
async def test_an_account_already_set_up_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, email: str
) -> None:
    """Test adding an account that is already set up aborts, whatever the email's case."""
    mock_config_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await _submit(hass, result["flow_id"], email=email)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_more_accounts_can_be_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: FakeServer,
    mock_setup_entry: AsyncMock,  # stops the new entries from setting up
) -> None:
    """Test each new account gets an entry of its own, with a unique ID in lowercase."""
    mock_config_entry.add_to_hass(hass)
    first = await _submit(
        hass, (await _start(hass))["flow_id"], email="Other@Example.COM"
    )
    second = await _submit(
        hass, (await _start(hass))["flow_id"], email="third@example.com"
    )

    assert first["type"] is second["type"] is FlowResultType.CREATE_ENTRY
    assert first["result"].unique_id == "other@example.com"
    assert second["result"].unique_id == "third@example.com"
    assert first["data"][CONF_DEVICE_UUID] != second["data"][CONF_DEVICE_UUID]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 3
    # The default entry sets up with the first flow, then each new entry once.
    assert len(mock_setup_entry.mock_calls) == 3
