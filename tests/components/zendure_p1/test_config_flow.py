"""Test the Zendure Smart Meter P1 config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from zendure_p1 import (
    ZendureP1ConnectionError,
    ZendureP1ResponseError,
    ZendureP1TimeoutError,
)

from homeassistant.components.zendure_p1.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import mock_client as _mock_client


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and can successfully set up the integration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.zendure_p1.config_flow.ZendureP1Client",
        return_value=_mock_client(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SN123456"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the same device cannot be configured twice."""
    with patch(
        "homeassistant.components.zendure_p1.config_flow.ZendureP1Client",
        return_value=_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    with patch(
        "homeassistant.components.zendure_p1.config_flow.ZendureP1Client",
        return_value=_mock_client(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.101"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(
            ZendureP1ConnectionError(), "cannot_connect", id="connection_error"
        ),
        pytest.param(ZendureP1TimeoutError(), "cannot_connect", id="timeout_error"),
        pytest.param(ZendureP1ResponseError(), "cannot_connect", id="response_error"),
        pytest.param(Exception(), "unknown", id="unknown_error"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test we handle errors and the flow can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    failing_client = _mock_client()
    failing_client.get_report.side_effect = exception

    with patch(
        "homeassistant.components.zendure_p1.config_flow.ZendureP1Client",
        return_value=failing_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    with patch(
        "homeassistant.components.zendure_p1.config_flow.ZendureP1Client",
        return_value=_mock_client(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1
