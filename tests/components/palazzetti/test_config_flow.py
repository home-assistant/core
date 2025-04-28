"""Test the Palazzetti config flow."""

from unittest.mock import AsyncMock

from pypalazzetti.exceptions import CommunicationError

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant, mock_palazzetti_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stove"
    assert result["data"] == {CONF_HOST: "192.168.1.1"}
    assert result["result"].unique_id == "11:22:33:44:55:66"
    assert len(mock_palazzetti_client.connect.mock_calls) > 0


async def test_invalid_host(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test cannot connect error."""

    mock_palazzetti_client.connect.side_effect = CommunicationError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_palazzetti_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_flow(
    hass: HomeAssistant, mock_palazzetti_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the DHCP flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="connbox1234", ip="192.168.1.1", macaddress="11:22:33:44:55:66"
        ),
        context={"source": SOURCE_DHCP},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stove"
    assert result["result"].unique_id == "11:22:33:44:55:66"


async def test_dhcp_flow_error(
    hass: HomeAssistant, mock_palazzetti_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the DHCP flow."""
    mock_palazzetti_client.connect.side_effect = CommunicationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="connbox1234", ip="192.168.1.1", macaddress="11:22:33:44:55:66"
        ),
        context={"source": SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
