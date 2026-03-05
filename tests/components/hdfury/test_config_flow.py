"""Test the HDFury config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from hdfury import HDFuryError

from homeassistant.components.hdfury.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.123"),
    ip_addresses=[ip_address("192.168.1.123")],
    hostname="VRROOM-02.local.",
    name="VRROOM-02._http._tcp.local.",
    port=80,
    type="_http._tcp.local.",
    properties={
        "path": "/",
    },
)


async def test_async_step_user_gets_form_and_creates_entry(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that the we can view the form and that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.123"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
    }
    assert result["result"].unique_id == "000123456789"


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that we abort if we attempt to submit the same entry twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.123"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_successful_recovery_after_connection_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test error shown when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Simulate a connection error by raising a HDFuryError
    mock_hdfury_client.get_board.side_effect = HDFuryError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.123"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Simulate successful connection on retry
    mock_hdfury_client.get_board.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.123"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
    }
    assert result["result"].unique_id == "000123456789"


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
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
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
    }
    assert result["result"].unique_id == "000123456789"


async def test_zeroconf_flow_failure(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow failure."""

    # Simulate a connection error by raising a HDFuryError
    mock_hdfury_client.get_board.side_effect = HDFuryError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_abort_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf flow aborts with duplicate."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # Original entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.123"
    assert mock_config_entry.unique_id == "000123456789"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.124",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Changed entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.124"
    assert mock_config_entry.unique_id == "000123456789"


async def test_reconfigure_flow_no_change(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration without changing values."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # Original entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.123"
    assert mock_config_entry.unique_id == "000123456789"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.123",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Changed entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.123"
    assert mock_config_entry.unique_id == "000123456789"


async def test_reconfigure_flow_abort_incorrect_device(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ip of other device with different serial."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # Simulate different serial number, as if user entered wrong IP
    mock_hdfury_client.get_board.return_value = {
        "hostname": "VRROOM-21",
        "ipaddress": "192.168.1.124",
        "serial": "000987654321",
        "pcbv": "3",
        "version": "FW: 0.61",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.124",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "incorrect_device"

    # Entry should still be original entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.123"
    assert mock_config_entry.unique_id == "000123456789"


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration fails with cannot connect."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # Simulate a connection error by raising a HDFuryError
    mock_hdfury_client.get_board.side_effect = HDFuryError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.124",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["data_schema"]({}) == {CONF_HOST: "192.168.1.123"}

    # Attempt with valid IP should work
    mock_hdfury_client.get_board.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.124",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Changed entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.124"
    assert mock_config_entry.unique_id == "000123456789"
