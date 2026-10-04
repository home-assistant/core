"""Tests for the everHome/EcoTracker integration."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from homeassistant.components.everhome.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info import zeroconf

from tests.common import MockConfigEntry

IP_ADDRESS = "192.168.178.104"
NEW_IP_ADDRESS = "192.168.178.105"
DEVICE_ID = "abcdef123456"

ZEROCONF_DISCOVERY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address(IP_ADDRESS),
    ip_addresses=[ip_address(IP_ADDRESS)],
    hostname="ecotracker-E80690E0F2B4.local.",
    name="ecotracker-E80690E0F2B4",
    port=80,
    type="_everhome._tcp.",
    properties={"productid": 1137, "serial": "abcdef123456", "ip": IP_ADDRESS},
)


async def test_user_flow(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EcoTracker " + DEVICE_ID
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == DEVICE_ID


async def test_user_flow_error(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
) -> None:
    """Test full user configuration flow with connection error."""
    mock_everhome_client.async_update.return_value = False
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
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    mock_everhome_client.async_update.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: IP_ADDRESS},
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EcoTracker " + DEVICE_ID
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == DEVICE_ID


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
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
    assert result["title"] == "EcoTracker " + DEVICE_ID
    assert result["data"] == {CONF_HOST: IP_ADDRESS}
    assert result["result"].unique_id == DEVICE_ID


async def test_zeroconf_flow_error(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
) -> None:
    """Test zeroconf flow with connection error."""
    mock_everhome_client.async_update.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_no_serial(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf flow aborts when serial is missing from TXT record."""
    discovery_without_serial = zeroconf.ZeroconfServiceInfo(
        ip_address=ip_address(IP_ADDRESS),
        ip_addresses=[ip_address(IP_ADDRESS)],
        hostname="ecotracker-E80690E0F2B4.local.",
        name="ecotracker-E80690E0F2B4",
        port=80,
        type="_everhome._tcp.",
        properties={"productid": 1137, "ip": IP_ADDRESS},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_without_serial,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: NEW_IP_ADDRESS}


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow recovers from a connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_everhome_client.async_update.return_value = False

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_everhome_client.async_update.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: NEW_IP_ADDRESS}


async def test_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow aborts when pointed at a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_everhome_client.get_data.return_value.serial = "fedcba654321"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: NEW_IP_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {CONF_HOST: IP_ADDRESS}
