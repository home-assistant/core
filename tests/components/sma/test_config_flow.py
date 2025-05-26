"""Test the sma config flow."""

from unittest.mock import AsyncMock, patch

from pysma.exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
)
import pytest

from homeassistant.components.sma.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import (
    MOCK_DEVICE,
    MOCK_DHCP_DISCOVERY,
    MOCK_DHCP_DISCOVERY_INPUT,
    MOCK_USER_INPUT,
    MOCK_USER_REAUTH,
)

from tests.conftest import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="SMA123456",
    macaddress="0015BB00abcd",
)

DHCP_DISCOVERY_DUPLICATE = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="SMA123456789",
    macaddress="0015BB00abcd",
)


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_sma_client: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT["host"]
    assert result["data"] == MOCK_USER_INPUT

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SmaConnectionException, "cannot_connect"),
        (SmaAuthenticationException, "invalid_auth"),
        (SmaReadException, "cannot_retrieve_device_info"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sma.pysma.SMA.new_session", side_effect=exception
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_sma_client: AsyncMock
) -> None:
    """Test starting a flow by user when already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, unique_id="123456789")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery(
    hass: HomeAssistant, mock_setup_entry: MockConfigEntry, mock_sma_client: AsyncMock
) -> None:
    """Test we can setup from dhcp discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_DHCP_DISCOVERY_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DHCP_DISCOVERY["host"]
    assert result["data"] == MOCK_DHCP_DISCOVERY
    assert result["result"].unique_id == DHCP_DISCOVERY.hostname.replace("SMA", "")


async def test_dhcp_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a flow by dhcp when already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY_DUPLICATE
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SmaConnectionException, "cannot_connect"),
        (SmaAuthenticationException, "invalid_auth"),
        (SmaReadException, "cannot_retrieve_device_info"),
        (Exception, "unknown"),
    ],
)
async def test_dhcp_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
    mock_sma_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle cannot connect error in DHCP flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    with patch("homeassistant.components.sma.pysma.SMA") as mock_sma:
        mock_sma_instance = mock_sma.return_value
        mock_sma_instance.new_session = AsyncMock(side_effect=exception)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DHCP_DISCOVERY_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch("homeassistant.components.sma.pysma.SMA") as mock_sma:
        mock_sma_instance = mock_sma.return_value
        mock_sma_instance.new_session = AsyncMock(return_value=True)
        mock_sma_instance.device_info = AsyncMock(return_value=MOCK_DEVICE)
        mock_sma_instance.close_session = AsyncMock(return_value=True)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DHCP_DISCOVERY_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DHCP_DISCOVERY["host"]
    assert result["data"] == MOCK_DHCP_DISCOVERY
    assert result["result"].unique_id == DHCP_DISCOVERY.hostname.replace("SMA", "")


async def test_full_flow_reauth(
    hass: HomeAssistant, mock_setup_entry: MockConfigEntry, mock_sma_client: AsyncMock
) -> None:
    """Test the full flow of the config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, unique_id="123456789")
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # There is no user input
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_REAUTH,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SmaConnectionException, "cannot_connect"),
        (SmaAuthenticationException, "invalid_auth"),
        (SmaReadException, "cannot_retrieve_device_info"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors during reauth flow properly."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, unique_id="123456789")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch("homeassistant.components.sma.pysma.SMA") as mock_sma:
        mock_sma_instance = mock_sma.return_value
        mock_sma_instance.new_session = AsyncMock(side_effect=exception)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_REAUTH,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}
        assert result["step_id"] == "reauth_confirm"

        mock_sma_instance.new_session = AsyncMock(return_value=True)
        mock_sma_instance.device_info = AsyncMock(return_value=MOCK_DEVICE)
        mock_sma_instance.close_session = AsyncMock(return_value=True)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_REAUTH,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
