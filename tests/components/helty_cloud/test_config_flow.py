"""Test the Helty Flow Cloud config flow."""

from unittest.mock import AsyncMock

from pyheltycloud import HeltyCloudAuthError, HeltyCloudConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.helty_cloud.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import EMAIL, PASSWORD, USER_ID

USER_INPUT = {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}


async def test_full_flow(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == USER_ID


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (HeltyCloudAuthError, "invalid_auth"),
        (HeltyCloudConnectionError, "cannot_connect"),
    ],
)
async def test_flow_errors_and_recovery(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test the flow shows the error and recovers once the cloud answers."""
    mock_helty_cloud.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_helty_cloud.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_account(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same account cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_same_account_under_another_email(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an account is recognised by its id, not by the email it logs in with."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_EMAIL: "renamed@example.com"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
