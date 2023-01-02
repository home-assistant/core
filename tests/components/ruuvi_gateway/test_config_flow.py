"""Test the Ruuvi Gateway config flow."""
from unittest.mock import patch

from aioruuvigateway.excs import CannotConnect, InvalidAuth
import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.ruuvi_gateway.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .consts import BASE_DATA, EXPECTED_TITLE, GATEWAY_MAC, GET_GATEWAY_HISTORY_DATA
from .utils import patch_gateway_ok, patch_setup_entry_ok

DHCP_IP = "1.2.3.4"
DHCP_DATA = {**BASE_DATA, "host": DHCP_IP}


@pytest.mark.parametrize(
    "init_data, init_context, entry",
    [
        (
            None,
            {"source": config_entries.SOURCE_USER},
            BASE_DATA,
        ),
        (
            dhcp.DhcpServiceInfo(
                hostname="RuuviGateway1234",
                ip=DHCP_IP,
                macaddress="12:34:56:78:90:ab",
            ),
            {"source": config_entries.SOURCE_DHCP},
            DHCP_DATA,
        ),
    ],
    ids=["user", "dhcp"],
)
async def test_ok_setup(hass: HomeAssistant, init_data, init_context, entry) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=init_data,
        context=init_context,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER
    assert result["errors"] is None

    with patch_gateway_ok(), patch_setup_entry_ok() as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            entry,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == EXPECTED_TITLE
    assert result2["data"] == entry
    assert result2["context"]["unique_id"] == GATEWAY_MAC
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(GET_GATEWAY_HISTORY_DATA, side_effect=InvalidAuth):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            BASE_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(GET_GATEWAY_HISTORY_DATA, side_effect=CannotConnect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            BASE_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected(hass: HomeAssistant) -> None:
    """Test we handle unexpected errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(GET_GATEWAY_HISTORY_DATA, side_effect=MemoryError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            BASE_DATA,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
