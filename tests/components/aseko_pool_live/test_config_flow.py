"""Test the Aseko Pool Live config flow."""

from unittest.mock import patch

from aioaseko import AccountInfo, APIUnavailable, InvalidAuthCredentials
import pytest

from homeassistant import config_entries
from homeassistant.components.aseko_pool_live.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_async_step_user_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_async_step_user_success(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.aseko_pool_live.config_flow.WebAccount.login",
            return_value=AccountInfo("aseko@example.com", "a_user_id", "any_language"),
        ),
        patch(
            "homeassistant.components.aseko_pool_live.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "aseko@example.com",
                CONF_PASSWORD: "passw0rd",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "aseko@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "aseko@example.com",
        CONF_PASSWORD: "passw0rd",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_web", "reason"),
    [
        (APIUnavailable, "cannot_connect"),
        (InvalidAuthCredentials, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_async_step_user_exception(
    hass: HomeAssistant, error_web: Exception, reason: str
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aseko_pool_live.config_flow.WebAccount.login",
        return_value=AccountInfo("aseko@example.com", "a_user_id", "any_language"),
        side_effect=error_web,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "aseko@example.com",
                CONF_PASSWORD: "passw0rd",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": reason}


@pytest.mark.parametrize(
    ("error_web", "reason"),
    [
        (APIUnavailable, "cannot_connect"),
        (InvalidAuthCredentials, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_get_account_info_exceptions(
    hass: HomeAssistant, error_web: Exception, reason: str
) -> None:
    """Test we handle config flow exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aseko_pool_live.config_flow.WebAccount.login",
        return_value=AccountInfo("aseko@example.com", "a_user_id", "any_language"),
        side_effect=error_web,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "aseko@example.com",
                CONF_PASSWORD: "passw0rd",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": reason}


async def test_async_step_reauth_success(hass: HomeAssistant) -> None:
    """Test successful reauthentication."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UID",
        data={CONF_EMAIL: "aseko@example.com"},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aseko_pool_live.config_flow.WebAccount.login",
        return_value=AccountInfo("aseko@example.com", "a_user_id", "any_language"),
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "aseko@example.com", CONF_PASSWORD: "passw0rd"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_web", "reason"),
    [
        (APIUnavailable, "cannot_connect"),
        (InvalidAuthCredentials, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_async_step_reauth_exception(
    hass: HomeAssistant, error_web: Exception, reason: str
) -> None:
    """Test we get the form."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UID",
        data={CONF_EMAIL: "aseko@example.com"},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.aseko_pool_live.config_flow.WebAccount.login",
        return_value=AccountInfo("aseko@example.com", "a_user_id", "any_language"),
        side_effect=error_web,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "aseko@example.com",
                CONF_PASSWORD: "passw0rd",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": reason}
