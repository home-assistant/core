"""Test the IOmeter config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from iometer import IOmeterConnectionError

from homeassistant.components import zeroconf
from homeassistant.components.iometer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

IP_ADDRESS = "10.0.0.2"
IOMETER_DEVICE_ID = "658c2b34-2017-45f2-a12b-731235f8bb97"

ZEROCONF_DISCOVERY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address(IP_ADDRESS),
    ip_addresses=[ip_address(IP_ADDRESS)],
    hostname="IOmeter-EC63E8.local.",
    name="IOmeter-EC63E8",
    port=80,
    type="_iometer._tcp.",
    properties={},
)


async def test_user_flow(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
) -> None:
    """Test full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: IP_ADDRESS},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IOmeter 1ISK0000000000"
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == IOMETER_DEVICE_ID


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IOmeter 1ISK0000000000"
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == IOMETER_DEVICE_ID


async def test_zeroconf_flow_abort_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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


async def test_zeroconf_flow_connection_error(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    mock_iometer_client.get_current_status.side_effect = IOmeterConnectionError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_connection_error(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow error."""
    mock_iometer_client.get_current_status.side_effect = IOmeterConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_iometer_client.get_current_status.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_abort_duplicate(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: IP_ADDRESS},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
