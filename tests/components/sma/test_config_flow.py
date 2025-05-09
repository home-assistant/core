"""Test the sma config flow."""

from unittest.mock import patch

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
    _patch_async_setup_entry,
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


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch("pysma.SMA.new_session", return_value=True),
        patch("pysma.SMA.device_info", return_value=MOCK_DEVICE),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
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
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.sma.pysma.SMA.new_session", side_effect=exception
        ),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a flow by user when already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch("homeassistant.components.sma.pysma.SMA.new_session", return_value=True),
        patch(
            "homeassistant.components.sma.pysma.SMA.device_info",
            return_value=MOCK_DEVICE,
        ),
        patch(
            "homeassistant.components.sma.pysma.SMA.close_session", return_value=True
        ),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test we can setup from dhcp discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with (
        patch("homeassistant.components.sma.pysma.SMA.new_session", return_value=True),
        patch(
            "homeassistant.components.sma.pysma.SMA.device_info",
            return_value=MOCK_DEVICE,
        ),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DHCP_DISCOVERY_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DHCP_DISCOVERY["host"]
    assert result["data"] == MOCK_DHCP_DISCOVERY
    assert result["result"].unique_id == DHCP_DISCOVERY.hostname.replace("SMA", "")

    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a flow by dhcp when already configured."""
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
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    with patch(
        "homeassistant.components.sma.pysma.SMA.new_session", side_effect=exception
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DHCP_DISCOVERY_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with (
        patch("homeassistant.components.sma.pysma.SMA.new_session", return_value=True),
        patch(
            "homeassistant.components.sma.pysma.SMA.device_info",
            return_value=MOCK_DEVICE,
        ),
        patch(
            "homeassistant.components.sma.pysma.SMA.close_session", return_value=True
        ),
        _patch_async_setup_entry(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_DHCP_DISCOVERY_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DHCP_DISCOVERY["host"]
    assert result["data"] == MOCK_DHCP_DISCOVERY
    assert result["result"].unique_id == DHCP_DISCOVERY.hostname.replace("SMA", "")


async def test_full_flow_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the full flow of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # There is no user input
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch("pysma.SMA.new_session", return_value=True),
        patch("pysma.SMA.device_info", return_value=MOCK_DEVICE),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
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
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await mock_config_entry.start_reauth_flow(hass)

    with (
        patch("pysma.SMA.new_session", side_effect=exception),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_REAUTH,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert result["step_id"] == "reauth_confirm"
    assert len(mock_setup_entry.mock_calls) == 0

    with (
        patch("pysma.SMA.new_session", return_value=True),
        patch("pysma.SMA.device_info", return_value=MOCK_DEVICE),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_REAUTH,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1
