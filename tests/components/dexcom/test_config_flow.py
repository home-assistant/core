"""Test the Dexcom config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock

from pydexcom.errors import (
    AccountError,
    AccountErrorEnum,
    ServerError,
    ServerErrorEnum,
    SessionError,
    SessionErrorEnum,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONFIG_V2, TEST_ACCOUNT_ID, TEST_USERNAME, init_integration

from tests.common import MockConfigEntry


async def test_step_user(hass: HomeAssistant, mock_dexcom: MagicMock) -> None:
    """Test the user step."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        CONFIG_V2,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USERNAME
    assert result2["data"] == CONFIG_V2
    assert result2["result"].unique_id == TEST_ACCOUNT_ID


@pytest.mark.parametrize(
    "error",
    [
        AccountError(AccountErrorEnum.FAILED_AUTHENTICATION),
        SessionError(SessionErrorEnum.INVALID),
        ServerError(ServerErrorEnum.UNEXPECTED),
        Exception,
    ],
)
async def test_step_user_error(
    hass: HomeAssistant, error: Exception, mock_dexcom_gen: Generator[MagicMock]
) -> None:
    """Test we handle user step errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_dexcom_gen.side_effect = error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONFIG_V2,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "base": "invalid_auth" if isinstance(error, AccountError) else "unknown"
    }


async def test_step_user_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_dexcom: MagicMock
) -> None:
    """Test duplicate entry aborts."""

    await init_integration(hass, mock_config_entry)

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        CONFIG_V2,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
