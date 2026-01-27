"""Test the sma config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from pysma import SmaAuthenticationException, SmaConnectionException, SmaReadException
from pysma.helpers import DeviceInfo
import pytest

from homeassistant.components.sma.const import CONF_GROUP, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import (
    MOCK_DEVICE,
    MOCK_DHCP_DISCOVERY,
    MOCK_DHCP_DISCOVERY_INPUT,
    MOCK_USER_INPUT,
    MOCK_USER_REAUTH,
    MOCK_USER_RECONFIGURE,
)

from tests.conftest import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="SMA123456",
    macaddress="0015bb00abcd",
)

DHCP_DISCOVERY_DUPLICATE = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="SMA123456789",
    macaddress="0015bb00abcd",
)

DHCP_DISCOVERY_DUPLICATE_001 = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="SMA123456789-001",
    macaddress="0015bb00abcd",
)


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_sma_client: MagicMock
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
        "homeassistant.components.sma.config_flow.SMAWebConnect.new_session",
        side_effect=exception,
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


async def test_dhcp_already_configured_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a flow by DHCP when already configured and MAC is added."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert CONF_MAC not in mock_config_entry.data

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY_DUPLICATE_001,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert mock_config_entry.data.get(CONF_MAC) == format_mac(
        DHCP_DISCOVERY_DUPLICATE_001.macaddress
    )


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

    with patch("homeassistant.components.sma.config_flow.SMAWebConnect") as mock_sma:
        mock_sma_instance = mock_sma.return_value
        mock_sma_instance.new_session = AsyncMock(side_effect=exception)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DHCP_DISCOVERY_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch("homeassistant.components.sma.config_flow.SMAWebConnect") as mock_sma:
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

    with patch("homeassistant.components.sma.config_flow.SMAWebConnect") as mock_sma:
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


async def test_full_flow_reconfigure(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
    mock_sma_client: AsyncMock,
) -> None:
    """Test the full flow of the config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, unique_id="123456789")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "1.1.1.2"
    assert entry.data[CONF_SSL] is True
    assert entry.data[CONF_VERIFY_SSL] is False
    assert entry.data[CONF_GROUP] == "user"
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
async def test_full_flow_reconfigure_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
    mock_sma_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle cannot connect error and recover from it."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, unique_id="123456789")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_sma_client.new_session.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_sma_client.new_session.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "1.1.1.2"
    assert entry.data[CONF_SSL] is True
    assert entry.data[CONF_VERIFY_SSL] is False
    assert entry.data[CONF_GROUP] == "user"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_mismatch_id(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
    mock_sma_client: AsyncMock,
) -> None:
    """Test when a mismatch happens during reconfigure."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, unique_id="123456789")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # New device, on purpose to demonstrate we can't switch
    different_device = DeviceInfo(
        manufacturer="SMA",
        name="Different SMA Device",
        type="Sunny Boy 5.0",
        serial=987654321,
        sw_version="2.0.0",
    )
    mock_sma_client.device_info = AsyncMock(return_value=different_device)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
