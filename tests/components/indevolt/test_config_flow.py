"""Tests the Indevolt config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant.components.indevolt.const import DOMAIN
from homeassistant.config_entries import SOURCE_DISCOVERY, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_DEVICE_SN_GEN2, TEST_HOST

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_user_flow_success(hass: HomeAssistant, mock_indevolt: AsyncMock) -> None:
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
    assert result["data"]["host"] == TEST_HOST
    assert result["data"]["sn"] == TEST_DEVICE_SN_GEN2
    assert result["data"]["device_model"] == "CMS-SF2000"
    assert result["data"]["generation"] == 2
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
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection errors in user flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Configure mock to raise exception
    mock_indevolt.get_config.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Test recovery by patching the library to work
    mock_indevolt.get_config.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INDEVOLT CMS-SF2000"
    assert result["data"]["host"] == TEST_HOST
    assert result["data"]["sn"] == TEST_DEVICE_SN_GEN2


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
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_flow_success(
    hass: HomeAssistant, mock_indevolt: AsyncMock
) -> None:
    """Test successful discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data={"host": TEST_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"]["host"] == TEST_HOST
    assert result["description_placeholders"]["type"] == "CMS-SF2000"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "INDEVOLT CMS-SF2000"
    assert result["data"]["host"] == TEST_HOST
    assert result["data"]["sn"] == TEST_DEVICE_SN_GEN2


async def test_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_indevolt: AsyncMock
) -> None:
    """Test discovery aborts if already configured."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data={"host": TEST_HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_ip_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_indevolt: AsyncMock
) -> None:
    """Test discovery updates config entry IP if changed."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["host"] == TEST_HOST

    # Configure to mock different ip
    new_host = "192.168.1.200"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data={"host": new_host},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data["host"] == new_host


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (TimeoutError, "cannot_connect"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
    ],
)
async def test_discovery_cannot_connect(
    hass: HomeAssistant, mock_indevolt: AsyncMock, exception: Exception, reason: str
) -> None:
    """Test discovery aborts on connection errors."""

    # Configure mock to raise exception
    mock_indevolt.get_config.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data={"host": TEST_HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
