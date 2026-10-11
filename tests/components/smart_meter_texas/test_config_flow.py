"""Test the Smart Meter Texas config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

from aiohttp import ClientError
import pytest
from smart_meter_texas.exceptions import (
    SmartMeterTexasAPIError,
    SmartMeterTexasAuthError,
)

from homeassistant import config_entries
from homeassistant.components.smart_meter_texas.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_LOGIN = {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}


@contextmanager
def _patch_success() -> Generator[None]:
    """Patch a successful login and the entry setup."""
    with (
        patch("smart_meter_texas.Client.authenticate", return_value=True),
        patch(
            "homeassistant.components.smart_meter_texas.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch("smart_meter_texas.Client.authenticate", return_value=True),
        patch(
            "homeassistant.components.smart_meter_texas.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_LOGIN
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_LOGIN[CONF_USERNAME]
    assert result2["data"] == TEST_LOGIN
    assert result2["result"].unique_id == TEST_LOGIN[CONF_USERNAME]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "smart_meter_texas.Client.authenticate",
        side_effect=SmartMeterTexasAuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_LOGIN,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_LOGIN
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "side_effect", [TimeoutError, ClientError, SmartMeterTexasAPIError]
)
async def test_form_cannot_connect(
    hass: HomeAssistant, side_effect: type[Exception]
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "smart_meter_texas.Client.authenticate",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_LOGIN
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_LOGIN
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test base exception is handled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "smart_meter_texas.Client.authenticate",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_LOGIN,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_LOGIN
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_duplicate_account(hass: HomeAssistant) -> None:
    """Test that a duplicate account cannot be configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user123",
        data={"username": "user123", "password": "password123"},
    ).add_to_hass(hass)

    with patch(
        "smart_meter_texas.Client.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"username": "user123", "password": "password123"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth updates the password."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_LOGIN, unique_id=TEST_LOGIN[CONF_USERNAME]
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.smart_meter_texas.config_flow.Account"
        ) as mock_account,
        _patch_success(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )
        await hass.async_block_till_done()

    mock_account.assert_called_once_with("test-username", "new-password")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == TEST_LOGIN | {CONF_PASSWORD: "new-password"}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(SmartMeterTexasAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
        pytest.param(ClientError, "cannot_connect", id="client_error"),
        pytest.param(SmartMeterTexasAPIError, "cannot_connect", id="api_error"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: type[Exception], error: str
) -> None:
    """Test reauth handles errors and can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_LOGIN, unique_id=TEST_LOGIN[CONF_USERNAME]
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch("smart_meter_texas.Client.authenticate", side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"
