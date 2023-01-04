"""Test the ViCare config flow."""
from unittest.mock import MagicMock

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp
from homeassistant.components.vicare.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, MOCK_MAC

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: bool, mock_vicare_2_gas_boilers: MagicMock
):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert len(result["errors"]) == 0

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ViCare"
    assert result2["data"] == ENTRY_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_login(
    hass: HomeAssistant,
    mock_setup_entry: bool,
    mock_vicare_login_invalid_credentials_config_flow,
) -> None:
    """Test a flow with an invalid Vicare login."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT


async def test_form_dhcp(
    hass: HomeAssistant, mock_setup_entry: bool, mock_vicare_login_config_flow
):
    """Test we can setup from dhcp."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            hostname="mock_hostname",
            macaddress=MOCK_MAC,
        ),
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "foo@bar.com",
            CONF_PASSWORD: "1234",
            CONF_CLIENT_ID: "5678",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "ViCare"
    assert result2["data"] == ENTRY_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            hostname="mock_hostname",
            macaddress=MOCK_MAC,
        ),
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_input_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data=ENTRY_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
