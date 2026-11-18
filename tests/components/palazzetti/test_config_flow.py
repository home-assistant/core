"""Test the Palazzetti config flow."""

from unittest.mock import AsyncMock

from pypalazzetti.exceptions import CommunicationError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow(
    hass: HomeAssistant, mock_palazzetti_client: AsyncMock
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_invalid_host(
    hass: HomeAssistant, mock_palazzetti_client: AsyncMock
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_flow(
    hass: HomeAssistant, mock_palazzetti_client: AsyncMock
) -> None:
    """Test the DHCP flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="connbox1234", ip="192.168.1.1", macaddress="112233445566"
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_flow_error(
    hass: HomeAssistant, mock_palazzetti_client: AsyncMock
) -> None:
    """Test the DHCP flow."""
    mock_palazzetti_client.connect.side_effect = CommunicationError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="connbox1234", ip="192.168.1.1", macaddress="112233445566"
        ),
        context={"source": SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_already_configured(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="connbox1234", ip="192.168.1.1", macaddress="112233445566"
        ),
        context={"source": SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow updates the connection settings."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: "192.168.1.200"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow recovers after connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_palazzetti_client.connect.side_effect = CommunicationError()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_palazzetti_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: "192.168.1.200"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_palazzetti_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow aborts when the host belongs to another device."""
    mock_config_entry.add_to_hass(hass)
    mock_palazzetti_client.mac = "AA:BB:CC:DD:EE:FF"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.200"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {CONF_HOST: "127.0.0.1"}
