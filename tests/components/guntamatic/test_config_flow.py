"""Test the guntamatic config flow."""

from unittest.mock import AsyncMock, MagicMock

from guntamatic.heater import NoSerialException
import pytest
import requests

from homeassistant.components.guntamatic.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import MOCK_DATA, MOCK_PARSE_DATA

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_heater: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Guntamatic Heater"
    assert result["data"] == {CONF_HOST: "1.1.1.1"}

    assert result["result"].unique_id == MOCK_DATA["Serial"][0]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (requests.exceptions.ConnectionError, "cannot_connect"),
        (NoSerialException, "bad_data"),
        (Exception("Unknown error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    side_effect: Exception,
    expected_error: str,
    mock_heater: MagicMock,
) -> None:
    """Test we handle errors correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_heater.parse_data.side_effect = (side_effect,)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover from error
    mock_heater.parse_data.side_effect = None
    mock_heater.parse_data.return_value = MOCK_PARSE_DATA
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_already_configured(
    hass: HomeAssistant, mock_heater: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery(hass: HomeAssistant, mock_heater: MagicMock) -> None:
    """Test DHCP discovery shows confirmation form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.1.1.1",
            hostname="kessel0001",
            macaddress="0024bd123456",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
    assert result["result"].unique_id == MOCK_DATA["Serial"][0]


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (requests.exceptions.ConnectionError, "cannot_connect"),
        (NoSerialException, "bad_data"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_errors(
    hass: HomeAssistant,
    side_effect: Exception,
    expected_error: str,
    mock_heater: MagicMock,
) -> None:
    """Test DHCP discovery shows confirmation form."""
    mock_heater.parse_data.side_effect = (side_effect,)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.1.1.1",
            hostname="kessel0001",
            macaddress="0024bd123456",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error


async def test_dhcp_updates_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test DHCP discovery updates IP when device changes address."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="1.1.1.2",
            hostname="kessel0001",
            macaddress="0024bd123456",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "1.1.1.2"
    assert mock_config_entry.unique_id == MOCK_DATA["Serial"][0]
