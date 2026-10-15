"""Test the Dexcom config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

from pydexcom import Region
from pydexcom.errors import AccountError, SessionError
import pytest

from homeassistant import config_entries
from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONFIG

from tests.common import MockConfigEntry


@contextmanager
def _patch_success() -> Generator[None]:
    """Patch the Dexcom client and entry setup."""
    with (
        patch("homeassistant.components.dexcom.config_flow.Dexcom"),
        patch("homeassistant.components.dexcom.async_setup_entry", return_value=True),
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
        patch("homeassistant.components.dexcom.config_flow.Dexcom"),
        patch(
            "homeassistant.components.dexcom.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONFIG[CONF_USERNAME]
    assert result2["data"] == CONFIG
    assert result2["result"].unique_id == CONFIG[CONF_USERNAME]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_account_error(hass: HomeAssistant) -> None:
    """Test we handle account error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dexcom.config_flow.Dexcom",
        side_effect=AccountError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_session_error(hass: HomeAssistant) -> None:
    """Test we handle session error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dexcom.config_flow.Dexcom",
        side_effect=SessionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dexcom.config_flow.Dexcom",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth updates the password."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG, unique_id=CONFIG[CONF_USERNAME])
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch("homeassistant.components.dexcom.config_flow.Dexcom") as mock_dexcom,
        patch("homeassistant.components.dexcom.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new_password"}
        )
        await hass.async_block_till_done()

    mock_dexcom.assert_called_once_with(
        username="test_username", password="new_password", region=Region.US
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == CONFIG | {CONF_PASSWORD: "new_password"}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(AccountError, "invalid_auth", id="invalid_auth"),
        pytest.param(SessionError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: type[Exception], error: str
) -> None:
    """Test reauth handles errors and can recover."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG, unique_id=CONFIG[CONF_USERNAME])
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.dexcom.config_flow.Dexcom",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong_password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new_password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_password"
