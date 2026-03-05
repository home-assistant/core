"""Tests the Indevolt config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant.components.indevolt.const import (
    CONF_GENERATION,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_DEVICE_SN_GEN2, TEST_HOST

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user-initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": TEST_HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INDEVOLT CMS-SF2000"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_SERIAL_NUMBER: TEST_DEVICE_SN_GEN2,
        CONF_MODEL: "CMS-SF2000",
        CONF_GENERATION: 2,
    }
    assert result["result"].unique_id == TEST_DEVICE_SN_GEN2


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection errors in user flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Configure mock to raise exception
    mock_indevolt.get_config.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Test recovery by patching the library to work
    mock_indevolt.get_config.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INDEVOLT CMS-SF2000"


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_indevolt: AsyncMock
) -> None:
    """Test duplicate entry aborts the flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Test duplicate entry creation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
