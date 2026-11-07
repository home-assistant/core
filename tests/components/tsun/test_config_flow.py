"""Tests for the TSUN config flow."""

from unittest.mock import ANY, AsyncMock

import pytest
from tsun_local_api import LoggerMetadata, TsunConnectionError, TsunProtocolError

from homeassistant.components.tsun import config_flow
from homeassistant.components.tsun.const import CONF_LOGGER_SN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, LOGGER_SN

from tests.common import MockConfigEntry

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: 8899}


async def test_user_flow(
    hass: HomeAssistant,
    mock_tsun_client: AsyncMock,
) -> None:
    """Test a complete user flow with automatic SN detection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TITAN"
    assert result["data"][CONF_LOGGER_SN] == LOGGER_SN
    assert result["data"][CONF_HOST] == HOST
    assert result["result"].unique_id == str(LOGGER_SN)
    config_flow.async_read_logger_metadata.assert_awaited_once_with(ANY, HOST)


async def test_manual_logger_sn_fallback(
    hass: HomeAssistant,
    mock_tsun_client: AsyncMock,
) -> None:
    """Test manual SN input when automatic reading is unavailable."""
    config_flow.async_read_logger_metadata.return_value = LoggerMetadata()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_detect_logger_sn"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_LOGGER_SN: LOGGER_SN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "metadata_error",
    [
        pytest.param(TsunConnectionError("status page unavailable"), id="unavailable"),
        pytest.param(TsunProtocolError("invalid status page"), id="invalid"),
    ],
)
async def test_manual_logger_sn_bypasses_metadata_error(
    hass: HomeAssistant,
    mock_tsun_client: AsyncMock,
    metadata_error: Exception,
) -> None:
    """Test manual SN input when metadata discovery raises an error."""
    config_flow.async_read_logger_metadata.side_effect = metadata_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_detect_logger_sn"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_LOGGER_SN: LOGGER_SN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_metadata_unexpected_error(
    hass: HomeAssistant,
    mock_tsun_client: AsyncMock,
) -> None:
    """Test an unexpected metadata discovery error."""
    config_flow.async_read_logger_metadata.side_effect = RuntimeError("unexpected")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(
            TsunConnectionError("cannot connect"), "cannot_connect", id="connection"
        ),
        pytest.param(
            TsunProtocolError("invalid response"),
            "invalid_response",
            id="protocol",
        ),
        pytest.param(RuntimeError("unexpected"), "unknown", id="unexpected"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_tsun_client: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection errors."""
    mock_tsun_client.async_read.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_duplicate_updates_address(
    hass: HomeAssistant,
    mock_tsun_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate logger updates its local address and aborts."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.0.2.20"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.20"
