"""Test the Matrix config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.matrix.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG_DATA, TEST_MXID, TEST_PASSWORD

from tests.common import MockConfigEntry

CONF_HOMESERVER = "homeserver"


def _mock_try_login_success(
    homeserver: str, username: str, password: str, verify_ssl: bool
) -> tuple[str | None, str | None]:
    return None, TEST_MXID


def _mock_try_login_invalid_auth(
    homeserver: str, username: str, password: str, verify_ssl: bool
) -> tuple[str | None, str | None]:
    return "invalid_auth", None


def _mock_try_login_cannot_connect(
    homeserver: str, username: str, password: str, verify_ssl: bool
) -> tuple[str | None, str | None]:
    return "cannot_connect", None


async def test_user_flow_success(hass: HomeAssistant, mock_client: type) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.matrix.config_flow._try_login",
        side_effect=_mock_try_login_success,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOMESERVER: "https://matrix.example.com",
                CONF_USERNAME: TEST_MXID,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_MXID
    assert result["data"] == {
        CONF_HOMESERVER: "https://matrix.example.com",
        CONF_USERNAME: TEST_MXID,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_VERIFY_SSL: True,
    }


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test that invalid credentials show an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.matrix.config_flow._try_login",
        side_effect=_mock_try_login_invalid_auth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOMESERVER: "https://matrix.example.com",
                CONF_USERNAME: TEST_MXID,
                CONF_PASSWORD: "wrongpassword",
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test that a connection failure shows an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.matrix.config_flow._try_login",
        side_effect=_mock_try_login_cannot_connect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOMESERVER: "https://matrix.example.com",
                CONF_USERNAME: TEST_MXID,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate(hass: HomeAssistant) -> None:
    """Test that duplicate entries are aborted."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA, unique_id=TEST_MXID)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.matrix.config_flow._try_login",
        side_effect=_mock_try_login_success,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOMESERVER: "https://matrix.example.com",
                CONF_USERNAME: TEST_MXID,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test a successful reauth flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA, unique_id=TEST_MXID)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.matrix.config_flow._try_login",
        side_effect=_mock_try_login_success,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "newpassword"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "newpassword"


async def test_reauth_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test that invalid credentials during reauth show an error."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA, unique_id=TEST_MXID)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.matrix.config_flow._try_login",
        side_effect=_mock_try_login_invalid_auth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "wrongpassword"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
