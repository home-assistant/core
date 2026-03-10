"""Tests the Indevolt config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant.components.indevolt.const import (
    CONF_GENERATION,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_DEVICE_SN_GEN2, TEST_HOST

from tests.common import MockConfigEntry

# Used to mock host change
TEST_HOST_NEW = "192.168.1.200"


async def test_user_flow_success(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user-initiated config flow."""

    # Initiate user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Verify correct form is returned
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test config entry creation (with success)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": TEST_HOST}
    )

    # Verify entry is created with correct data
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

    # Initiate user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Configure mock to raise exception
    mock_indevolt.get_config.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify exception is thrown with correct error message
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Test recovery by patching the library to work
    mock_indevolt.get_config.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify entry is created with correct data
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INDEVOLT CMS-SF2000"


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_indevolt: AsyncMock
) -> None:
    """Test duplicate entry aborts the flow."""
    mock_config_entry.add_to_hass(hass)

    # Initiate user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Test duplicate entry creation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify flow is aborted with correct reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)

    # Initiate reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    # Verify correct form is returned
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Mock new host input
    new_host = TEST_HOST_NEW
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )

    # Verify flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Flush pending tasks
    await hass.async_block_till_done()

    # Verify entry is updated
    assert mock_config_entry.data[CONF_HOST] == new_host
    assert mock_config_entry.data[CONF_SERIAL_NUMBER] == TEST_DEVICE_SN_GEN2


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
async def test_reconfigure_flow_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection errors in reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    # Initiate reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    # Configure mock to raise exception
    mock_indevolt.get_config.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify exception is thrown with correct error message
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Test recovery by patching the library to work
    mock_indevolt.get_config.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify entry is created with correct data and flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Flush pending tasks
    await hass.async_block_till_done()


async def test_reconfigure_flow_different_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure aborts when connecting to a different device."""
    mock_config_entry.add_to_hass(hass)

    # Setup new device for configuration
    mock_indevolt.get_config.return_value = {
        "device": {
            "sn": "DIFFERENT-SERIAL-99999999",
            "type": "CMS-OTHER",
            "generation": 1,
            "fw": "1.0.0",
        }
    }

    # Initiate reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    # Configure mock to cause host collision with different device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST_NEW}
    )

    # Verify flow is aborted with correct reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"

    # Flush pending tasks
    await hass.async_block_till_done()
