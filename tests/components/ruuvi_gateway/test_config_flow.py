"""Test the Ruuvi Gateway config flow."""

from unittest.mock import patch

from aioruuvigateway.excs import CannotConnect, InvalidAuth
import pytest

from homeassistant import config_entries
from homeassistant.components.ruuvi_gateway.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .consts import (
    BASE_DATA,
    EXPECTED_TITLE,
    GATEWAY_MAC_LOWER,
    GET_GATEWAY_HISTORY_DATA,
)
from .utils import patch_gateway_ok, patch_setup_entry_ok

DHCP_IP = "1.2.3.4"
DHCP_DATA = {**BASE_DATA, "host": DHCP_IP}


@pytest.mark.parametrize(
    ("init_data", "init_context", "entry"),
    [
        (
            None,
            {"source": config_entries.SOURCE_USER},
            BASE_DATA,
        ),
        (
            DhcpServiceInfo(
                hostname="RuuviGateway1234",
                ip=DHCP_IP,
                macaddress="1234567890ab",
            ),
            {"source": config_entries.SOURCE_DHCP},
            DHCP_DATA,
        ),
    ],
    ids=["user", "dhcp"],
)
async def test_ok_setup(hass: HomeAssistant, init_data, init_context, entry) -> None:
    """Test we get the form."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=init_data,
        context=init_context,
    )
    assert init_result["type"] is FlowResultType.FORM
    assert init_result["step_id"] == config_entries.SOURCE_USER
    assert init_result["errors"] is None

    # Check that we can finalize setup
    with patch_gateway_ok(), patch_setup_entry_ok() as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            entry,
        )
        await hass.async_block_till_done()
    assert config_result["type"] is FlowResultType.CREATE_ENTRY
    assert config_result["title"] == EXPECTED_TITLE
    assert config_result["data"] == entry
    assert config_result["context"]["unique_id"] == GATEWAY_MAC_LOWER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(GET_GATEWAY_HISTORY_DATA, side_effect=InvalidAuth):
        config_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            BASE_DATA,
        )

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "invalid_auth"}

    # Check that we still can finalize setup
    with patch_gateway_ok(), patch_setup_entry_ok() as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            BASE_DATA,
        )
        await hass.async_block_till_done()
    assert config_result["type"] is FlowResultType.CREATE_ENTRY
    assert config_result["title"] == EXPECTED_TITLE
    assert config_result["data"] == BASE_DATA
    assert config_result["context"]["unique_id"] == GATEWAY_MAC_LOWER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(GET_GATEWAY_HISTORY_DATA, side_effect=CannotConnect):
        config_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            BASE_DATA,
        )

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "cannot_connect"}

    # Check that we still can finalize setup
    with patch_gateway_ok(), patch_setup_entry_ok() as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            BASE_DATA,
        )
        await hass.async_block_till_done()
    assert config_result["type"] is FlowResultType.CREATE_ENTRY
    assert config_result["title"] == EXPECTED_TITLE
    assert config_result["data"] == BASE_DATA
    assert config_result["context"]["unique_id"] == GATEWAY_MAC_LOWER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unexpected(hass: HomeAssistant) -> None:
    """Test we handle unexpected errors."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(GET_GATEWAY_HISTORY_DATA, side_effect=MemoryError):
        config_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            BASE_DATA,
        )

    assert config_result["type"] is FlowResultType.FORM
    assert config_result["errors"] == {"base": "unknown"}

    # Check that we still can finalize setup
    with patch_gateway_ok(), patch_setup_entry_ok() as mock_setup_entry:
        config_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            BASE_DATA,
        )
        await hass.async_block_till_done()
    assert config_result["type"] is FlowResultType.CREATE_ENTRY
    assert config_result["title"] == EXPECTED_TITLE
    assert config_result["data"] == BASE_DATA
    assert config_result["context"]["unique_id"] == GATEWAY_MAC_LOWER
    assert len(mock_setup_entry.mock_calls) == 1
