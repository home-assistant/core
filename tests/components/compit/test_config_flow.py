"""Test the Compit config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.compit.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.compit.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .consts import CONFIG_INPUT

from tests.common import MockConfigEntry


async def test_async_step_user_success(
    hass: HomeAssistant, mock_compit_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test user step with successful authentication."""
    mock_compit_api.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG_INPUT[CONF_EMAIL]
    assert result["data"] == CONFIG_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth(), "invalid_auth"),
        (CannotConnect(), "cannot_connect"),
        (Exception(), "unknown"),
        (False, "unknown"),
    ],
)
async def test_async_step_user_failed_auth(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
    mock_compit_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user step with invalid authentication then success after error is cleared."""
    mock_compit_api.side_effect = [exception, True]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Test success after error is cleared
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_INPUT
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG_INPUT[CONF_EMAIL]
    assert result["data"] == CONFIG_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_compit_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth step with successful authentication."""
    mock_compit_api.return_value = True

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_EMAIL: CONFIG_INPUT[CONF_EMAIL],
        CONF_PASSWORD: "new-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth(), "invalid_auth"),
        (CannotConnect(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_async_step_reauth_confirm_failed_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_error: str,
    mock_compit_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth confirm step with invalid authentication then success after error is cleared."""
    mock_compit_api.side_effect = [exception, True]

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Test success after error is cleared
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: CONFIG_INPUT[CONF_EMAIL], CONF_PASSWORD: "correct-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_EMAIL: CONFIG_INPUT[CONF_EMAIL],
        CONF_PASSWORD: "correct-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
