"""Test Goal Zero Yeti config flow."""
from unittest.mock import patch

from goalzero import exceptions

from homeassistant import data_entry_flow
from homeassistant.components.goalzero.const import DEFAULT_NAME, DOMAIN, MANUFACTURER
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.core import HomeAssistant

from . import (
    CONF_DATA,
    CONF_DHCP_FLOW,
    MAC,
    create_entry,
    create_mocked_yeti,
    patch_config_flow_yeti,
)


def _patch_setup():
    return patch("homeassistant.components.goalzero.async_setup_entry")


async def test_flow_user(hass: HomeAssistant):
    """Test user initialized flow."""
    mocked_yeti = await create_mocked_yeti()
    with patch_config_flow_yeti(mocked_yeti), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONF_DATA
        assert result["result"].unique_id == MAC


async def test_flow_user_already_configured(hass: HomeAssistant):
    """Test user initialized flow with duplicate server."""
    create_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    with patch_config_flow_yeti(await create_mocked_yeti()) as yetimock:
        yetimock.side_effect = exceptions.ConnectError
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user_invalid_host(hass: HomeAssistant):
    """Test user initialized flow with invalid server."""
    with patch_config_flow_yeti(await create_mocked_yeti()) as yetimock:
        yetimock.side_effect = exceptions.InvalidHost
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "invalid_host"


async def test_flow_user_unknown_error(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    with patch_config_flow_yeti(await create_mocked_yeti()) as yetimock:
        yetimock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"


async def test_dhcp_discovery(hass: HomeAssistant):
    """Test we can process the discovery from dhcp."""

    mocked_yeti = await create_mocked_yeti()
    with patch_config_flow_yeti(mocked_yeti), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=CONF_DHCP_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == MANUFACTURER
        assert result["data"] == CONF_DATA
        assert result["result"].unique_id == MAC

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=CONF_DHCP_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_dhcp_discovery_failed(hass: HomeAssistant):
    """Test failed setup from dhcp."""
    mocked_yeti = await create_mocked_yeti()
    with patch_config_flow_yeti(mocked_yeti) as yetimock:
        yetimock.side_effect = exceptions.ConnectError
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=CONF_DHCP_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"

    with patch_config_flow_yeti(mocked_yeti) as yetimock:
        yetimock.side_effect = exceptions.InvalidHost
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=CONF_DHCP_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "invalid_host"

    with patch_config_flow_yeti(mocked_yeti) as yetimock:
        yetimock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=CONF_DHCP_FLOW,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "unknown"
