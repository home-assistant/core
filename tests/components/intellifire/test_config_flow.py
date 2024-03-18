"""Test the IntelliFire config flow."""

from unittest.mock import AsyncMock

from intellifire4py.model import IntelliFirePollData

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.intellifire.const import CONF_SERIAL, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_standard_config_with_single_fireplace(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_login_with_credentials: AsyncMock,
    mock_cloud_api_interface_user_data_1,
    mock_connectivity_test_pass_pass,
):
    """Test standard flow with a user who has only a single fireplace."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    # For a single fireplace we just create it
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_standard_config_with_pre_configured_fireplace(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_login_with_credentials: AsyncMock,
    mock_config_entry_current,
    mock_cloud_api_interface_user_data_1,
    mock_connectivity_test_pass_pass,
):
    """What if we try to configure an already configured fireplace."""
    # Configure an existing entry
    mock_config_entry_current.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )

    # For a single fireplace we just create it
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "all_devices_already_configured"


async def test_standard_config_with_single_fireplace_and_bad_credentials(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_login_with_bad_credentials: AsyncMock,
    mock_cloud_api_interface_user_data_1,
    mock_connectivity_test_pass_pass,
):
    """Run a test against bad crednetials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "api_error"}
    assert result["step_id"] == "cloud_api"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    # For a single fireplace we just create it
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_standard_config_with_multiple_fireplace(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_login_with_credentials: AsyncMock,
    mock_cloud_api_interface_user_data_3,
    mock_connectivity_test_pass_pass,
):
    """Test multi-fireplace user who must be very rich."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    # When we have multiple fireplaces we get to pick a serial
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_cloud_device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SERIAL: "4GC295860E5837G40D9974B7FD459234"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "ip_address": "192.168.2.109",
        "api_key": "D4C5EB28BBFF41E1FB21AFF9BFA6CD34",
        "serial": "4GC295860E5837G40D9974B7FD459234",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_dhcp_discovery_intellifire_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_poll_local_fireplace: AsyncMock,
    mock_login_with_credentials: AsyncMock,
    mock_local_poll_data: IntelliFirePollData,
    mock_cloud_api_interface_user_data_3,
) -> None:
    """Test successful DHCP Discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="aabbcceeddff",
            hostname="zentrios-Test",
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cloud_api"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "donJulio", CONF_PASSWORD: "Tequila0FD00m"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_dhcp_discovery_non_intellifire_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_poll_local_fireplace_exception: AsyncMock,
    mock_login_with_credentials: AsyncMock,
    mock_local_poll_data: IntelliFirePollData,
    mock_cloud_api_interface_user_data_3,
) -> None:
    """Test successful DHCP Discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="aabbcceeddff",
            hostname="zentrios-Evil",
        ),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_intellifire_device"
