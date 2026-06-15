"""Test the Aquacell config flow."""

from datetime import datetime
from unittest.mock import AsyncMock

from aioaquacell import ApiException, AuthenticationFailed
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.aquacell.const import (
    CONF_BRAND,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_CONFIG_ENTRY, TEST_USER_INPUT

from tests.common import MockConfigEntry


async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Test already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **TEST_CONFIG_ENTRY,
        },
        unique_id=TEST_CONFIG_ENTRY[CONF_EMAIL],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_aquacell_api: AsyncMock
) -> None:
    """Test the full config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_CONFIG_ENTRY[CONF_EMAIL]
    assert result2["data"][CONF_EMAIL] == TEST_CONFIG_ENTRY[CONF_EMAIL]
    assert result2["data"][CONF_PASSWORD] == TEST_CONFIG_ENTRY[CONF_PASSWORD]
    assert result2["data"][CONF_REFRESH_TOKEN] == TEST_CONFIG_ENTRY[CONF_REFRESH_TOKEN]
    assert result2["data"][CONF_BRAND] == TEST_CONFIG_ENTRY[CONF_BRAND]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ApiException, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (AuthenticationFailed, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_setup_entry: AsyncMock,
    mock_aquacell_api: AsyncMock,
) -> None:
    """Test we handle form exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_aquacell_api.authenticate.side_effect = exception
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    mock_aquacell_api.authenticate.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == TEST_CONFIG_ENTRY[CONF_EMAIL]
    assert result3["data"][CONF_EMAIL] == TEST_CONFIG_ENTRY[CONF_EMAIL]
    assert result3["data"][CONF_PASSWORD] == TEST_CONFIG_ENTRY[CONF_PASSWORD]
    assert result3["data"][CONF_REFRESH_TOKEN] == TEST_CONFIG_ENTRY[CONF_REFRESH_TOKEN]
    assert result3["data"][CONF_BRAND] == TEST_CONFIG_ENTRY[CONF_BRAND]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_setup_entry: AsyncMock,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauthentication flow."""
    freezer.move_to("2024-01-01 00:00:00+00:00")
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "refresh-token"
    assert (
        mock_config_entry.data[CONF_REFRESH_TOKEN_CREATION_TIME]
        == datetime.now().timestamp()
    )


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ApiException, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (AuthenticationFailed, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_setup_entry: AsyncMock,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle exceptions in the reauth flow and can recover."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_aquacell_api.authenticate.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_aquacell_api.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
