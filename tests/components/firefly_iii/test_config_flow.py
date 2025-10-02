"""Test the Firefly III config flow."""

from unittest.mock import AsyncMock, MagicMock

from pyfirefly.exceptions import (
    FireflyAuthenticationError,
    FireflyConnectionError,
    FireflyTimeoutError,
)
import pytest

from homeassistant.components.firefly_iii.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_TEST_CONFIG

from tests.common import MockConfigEntry

MOCK_USER_SETUP = {
    CONF_URL: "https://127.0.0.1:8080/",
    CONF_API_KEY: "test_api_key",
    CONF_VERIFY_SSL: True,
}


async def test_form_and_flow(
    hass: HomeAssistant,
    mock_firefly_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test we get the form and can complete the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "https://127.0.0.1:8080/"
    assert result["data"] == MOCK_TEST_CONFIG


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (
            FireflyAuthenticationError,
            "invalid_auth",
        ),
        (
            FireflyConnectionError,
            "cannot_connect",
        ),
        (
            FireflyTimeoutError,
            "timeout_connect",
        ),
        (
            Exception("Some other error"),
            "unknown",
        ),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_firefly_client: AsyncMock,
    mock_setup_entry: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions."""
    mock_firefly_client.get_about.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_firefly_client.get_about.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "https://127.0.0.1:8080/"
    assert result["data"] == MOCK_TEST_CONFIG


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_firefly_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle duplicate entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_SETUP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow_reauth(
    hass: HomeAssistant,
    mock_firefly_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the full flow of the config flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # There is no user input
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (
            FireflyAuthenticationError,
            "invalid_auth",
        ),
        (
            FireflyConnectionError,
            "cannot_connect",
        ),
        (
            FireflyTimeoutError,
            "timeout_connect",
        ),
        (
            Exception("Some other error"),
            "unknown",
        ),
    ],
)
async def test_reauth_flow_exceptions(
    hass: HomeAssistant,
    mock_firefly_client: AsyncMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all exceptions in the reauth flow."""
    mock_config_entry.add_to_hass(hass)
    mock_firefly_client.get_about.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    # Now test that we can recover from the error
    mock_firefly_client.get_about.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "new_api_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
    assert len(mock_setup_entry.mock_calls) == 1
