"""Test D-Link Smart Plug config flow."""
from unittest.mock import MagicMock, patch

from homeassistant import data_entry_flow
from homeassistant.components import dhcp
from homeassistant.components.dlink.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import (
    CONF_DATA,
    CONF_DHCP_DATA,
    CONF_DHCP_FLOW,
    CONF_DHCP_FLOW_NEW_IP,
    patch_config_flow,
)

from tests.common import MockConfigEntry


def _patch_setup_entry():
    return patch("homeassistant.components.dlink.async_setup_entry", return_value=True)


async def test_flow_user(hass: HomeAssistant, mocked_plug: MagicMock) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    with patch_config_flow(mocked_plug), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test user initialized flow with duplicate server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(
    hass: HomeAssistant,
    mocked_plug_legacy: MagicMock,
    mocked_plug_legacy_no_auth: MagicMock,
) -> None:
    """Test user initialized flow with unreachable server."""
    with patch_config_flow(mocked_plug_legacy_no_auth):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"

    with patch_config_flow(mocked_plug_legacy), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_unknown_error(
    hass: HomeAssistant, mocked_plug: MagicMock
) -> None:
    """Test user initialized flow with unreachable server."""
    with patch_config_flow(mocked_plug) as mock:
        mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "unknown"

    with patch_config_flow(mocked_plug), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


async def test_dhcp(hass: HomeAssistant, mocked_plug: MagicMock) -> None:
    """Test we can process the discovery from dhcp."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=CONF_DHCP_FLOW
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"
    with patch_config_flow(mocked_plug), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DHCP_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


async def test_dhcp_failed_legacy_auth(
    hass: HomeAssistant, mocked_plug: MagicMock, mocked_plug_legacy_no_auth: MagicMock
) -> None:
    """Test we can recover from failed legacy authentication during dhcp flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=CONF_DHCP_FLOW
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"
    with patch_config_flow(mocked_plug_legacy_no_auth):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DHCP_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    with patch_config_flow(mocked_plug), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DHCP_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


async def test_dhcp_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test dhcp initialized flow with duplicate server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=CONF_DHCP_FLOW
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.unique_id == "aa:bb:cc:dd:ee:ff"


async def test_dhcp_unique_id_assignment(
    hass: HomeAssistant, mocked_plug: MagicMock
) -> None:
    """Test dhcp initialized flow with no unique id for matching entry."""
    dhcp_data = dhcp.DhcpServiceInfo(
        ip="2.3.4.5",
        macaddress="11:22:33:44:55:66",
        hostname="dsp-w215",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=dhcp_data
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"
    with patch_config_flow(mocked_plug), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DHCP_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == CONF_DATA | {CONF_HOST: "2.3.4.5"}
    assert result["result"].unique_id == "11:22:33:44:55:66"


async def test_dhcp_changed_ip(
    hass: HomeAssistant, config_entry_with_uid: MockConfigEntry
) -> None:
    """Test that we successfully change IP address for device with known mac address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=CONF_DHCP_FLOW_NEW_IP
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_with_uid.data[CONF_HOST] == "5.6.7.8"
