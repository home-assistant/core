"""Tests for the SunSynk config flow."""

from __future__ import annotations

from unittest.mock import patch

from custom_components.sunsynk.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLANT_IGNORE_LIST,
    CONF_REGION,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SunSynkAuthError,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

VALID_USER_INPUT = {
    CONF_REGION: 0,
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "secret123",
}


@pytest.fixture
def mock_authenticate():
    """Mock the authenticate function."""
    with patch(
        "custom_components.sunsynk.config_flow.async_authenticate",
    ) as mock_auth:
        yield mock_auth


async def test_user_flow_success(hass: HomeAssistant, mock_authenticate) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SunSynk (test@example.com)"
    assert result["data"] == VALID_USER_INPUT


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_authenticate) -> None:
    """Test config flow when API is unreachable."""
    mock_authenticate.side_effect = ConnectionError("timeout")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_authenticate) -> None:
    """Test config flow with invalid credentials."""
    mock_authenticate.side_effect = SunSynkAuthError("bad credentials")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test config flow with unexpected exception bypassing validate_input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.sunsynk.config_flow.validate_input",
        side_effect=RuntimeError("something weird"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_user_flow_recover_after_error(
    hass: HomeAssistant, mock_authenticate
) -> None:
    """Test that the user can retry after an error."""
    mock_authenticate.side_effect = SunSynkAuthError("bad password")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Now succeed on retry
    mock_authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_account(
    hass: HomeAssistant, mock_authenticate
) -> None:
    """Test abort when account is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow for update interval and plant ignore list."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_UPDATE_INTERVAL: 120,
            CONF_PLANT_IGNORE_LIST: "123,456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == 120
    assert entry.options[CONF_PLANT_IGNORE_LIST] == "123,456"


async def test_options_flow_defaults(hass: HomeAssistant) -> None:
    """Test that options flow shows current values as defaults."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
        options={
            CONF_UPDATE_INTERVAL: 90,
            CONF_PLANT_IGNORE_LIST: "789",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    # Submit with new values
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            CONF_PLANT_IGNORE_LIST: "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == DEFAULT_UPDATE_INTERVAL
    assert entry.options[CONF_PLANT_IGNORE_LIST] == ""


async def test_reauth_flow_success(hass: HomeAssistant, mock_authenticate) -> None:
    """Test successful re-authentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "newpass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_EMAIL] == "new@example.com"
    assert entry.data[CONF_PASSWORD] == "newpass"


async def test_reauth_flow_invalid_auth(hass: HomeAssistant, mock_authenticate) -> None:
    """Test re-authentication flow with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_authenticate.side_effect = SunSynkAuthError("bad creds")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "wrong",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant, mock_authenticate
) -> None:
    """Test re-authentication flow when API is unreachable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    mock_authenticate.side_effect = ConnectionError("timeout")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "secret123",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test re-authentication flow with unexpected exception."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "custom_components.sunsynk.config_flow.validate_input",
        side_effect=RuntimeError("something weird"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "secret123",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_reconfigure_flow_success(hass: HomeAssistant, mock_authenticate) -> None:
    """Test successful reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_REGION: 1,
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "newpass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_REGION] == 1
    assert entry.data[CONF_EMAIL] == "new@example.com"
    assert entry.data[CONF_PASSWORD] == "newpass"


async def test_reconfigure_flow_invalid_auth(
    hass: HomeAssistant, mock_authenticate
) -> None:
    """Test reconfiguration flow with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_authenticate.side_effect = SunSynkAuthError("bad creds")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_REGION: 0,
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "wrong",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, mock_authenticate
) -> None:
    """Test reconfiguration flow when API is unreachable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_authenticate.side_effect = ConnectionError("timeout")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_REGION: 0,
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "secret123",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test reconfiguration flow with unexpected exception."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=VALID_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "custom_components.sunsynk.config_flow.validate_input",
        side_effect=RuntimeError("something weird"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_REGION: 0,
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "secret123",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
