"""Tests for the WyBot config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wybot import WybotAuthError, WybotConnectionError

from homeassistant import config_entries
from homeassistant.components.wybot.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER = "pool@example.com"
PASSWORD = "hunter2"
USER_ID = "account-123"


def _client(user_id: str = USER_ID, authenticate=None) -> MagicMock:
    """Build a mock WyBotHTTPClient."""
    client = MagicMock()
    client.user_id = user_id
    if authenticate is not None:
        client.authenticate = AsyncMock(side_effect=authenticate)
    else:
        client.authenticate = AsyncMock(return_value=True)
    return client


def _patch_client(client: MagicMock):
    """Patch the config-flow HTTP client."""
    return patch(
        "homeassistant.components.wybot.config_flow.WyBotHTTPClient",
        return_value=client,
    )


def _patch_setup():
    """Patch async_setup_entry so the flow does not fully set up."""
    return patch("homeassistant.components.wybot.async_setup_entry", return_value=True)


def _entry(**kwargs) -> MockConfigEntry:
    """Build an existing account config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=kwargs.pop("unique_id", USER_ID),
        data={CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD, **kwargs},
    )


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """A valid account creates an entry keyed on the account id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with _patch_client(_client()), _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER
    assert result["data"][CONF_USERNAME] == USER
    assert result["result"].unique_id == USER_ID


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (WybotAuthError, "invalid_auth"),
        (WybotConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_errors_and_recovery(
    hass: HomeAssistant, side_effect: type[Exception], expected: str
) -> None:
    """Typed client errors map to form errors, then a retry succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_client(_client(authenticate=side_effect)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    with _patch_client(_client()), _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_account_aborts(hass: HomeAssistant) -> None:
    """The same account cannot be configured twice."""
    _entry().add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _patch_client(_client()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USER, CONF_PASSWORD: PASSWORD}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Reauth updates the stored password and reloads the entry."""
    entry = _entry(**{CONF_PASSWORD: "old"})
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with _patch_client(_client(user_id=USER_ID)), _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"


async def test_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Reauthenticating with a different account is rejected."""
    entry = _entry(**{CONF_PASSWORD: "old"})
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    with _patch_client(_client(user_id="different-account")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reauth_invalid_auth(hass: HomeAssistant) -> None:
    """A bad password during reauth shows an error and stays on the form."""
    entry = _entry(**{CONF_PASSWORD: "old"})
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    with _patch_client(_client(authenticate=WybotAuthError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "bad"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def _start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry):
    """Start a reconfigure flow."""
    return await entry.start_reconfigure_flow(hass)


async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Reconfigure updates the stored username/password and reloads the entry."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_user = "new@example.com"
    with _patch_client(_client(user_id=USER_ID)), _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: new_user, CONF_PASSWORD: "newpass"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_USERNAME] == new_user
    assert entry.data[CONF_PASSWORD] == "newpass"


async def test_reconfigure_wrong_account(hass: HomeAssistant) -> None:
    """Reconfiguring to a different account is rejected."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    with _patch_client(_client(user_id="different-account")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "other@example.com", CONF_PASSWORD: "newpass"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reconfigure_invalid_auth(hass: HomeAssistant) -> None:
    """Bad credentials during reconfigure show an error and stay on the form."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    with _patch_client(_client(authenticate=WybotAuthError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USER, CONF_PASSWORD: "bad"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (WybotConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: type[Exception], expected: str
) -> None:
    """Connection and unexpected errors during reauth show a form error."""
    entry = _entry(**{CONF_PASSWORD: "old"})
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    with _patch_client(_client(authenticate=side_effect)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "bad"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (WybotConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant, side_effect: type[Exception], expected: str
) -> None:
    """Connection and unexpected errors during reconfigure show a form error."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, entry)
    with _patch_client(_client(authenticate=side_effect)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USER, CONF_PASSWORD: "bad"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
