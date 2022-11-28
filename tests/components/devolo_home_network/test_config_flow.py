"""Test the devolo Home Network config flow."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from devolo_plc_api.exceptions.device import DeviceNotFound
import pytest

from homeassistant import config_entries
from homeassistant.components.devolo_home_network import config_flow
from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    SERIAL_NUMBER,
    TITLE,
)
from homeassistant.const import CONF_BASE, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DISCOVERY_INFO, DISCOVERY_INFO_WRONG_DEVICE, IP


async def test_form(hass: HomeAssistant, info: dict[str, Any]):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.devolo_home_network.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: IP,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["result"].unique_id == info["serial_number"]
    assert result2["title"] == info["title"]
    assert result2["data"] == {
        CONF_IP_ADDRESS: IP,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "exception_type, expected_error",
    [[DeviceNotFound, "cannot_connect"], [Exception, "unknown"]],
)
async def test_form_error(hass: HomeAssistant, exception_type, expected_error):
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.devolo_home_network.config_flow.validate_input",
        side_effect=exception_type,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: IP,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_BASE: expected_error}


async def test_zeroconf(hass: HomeAssistant):
    """Test that the zeroconf form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"] == {"host_name": "test"}

    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )

    assert (
        context["title_placeholders"][CONF_NAME]
        == DISCOVERY_INFO.hostname.split(".", maxsplit=1)[0]
    )

    with patch(
        "homeassistant.components.devolo_home_network.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["title"] == "test"
    assert result2["data"] == {
        CONF_IP_ADDRESS: IP,
    }


async def test_abort_zeroconf_wrong_device(hass: HomeAssistant):
    """Test we abort zeroconf for wrong devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_WRONG_DEVICE,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "home_control"


@pytest.mark.usefixtures("info")
async def test_abort_if_configued(hass: HomeAssistant):
    """Test we abort config flow if already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.devolo_home_network.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: IP,
            },
        )
        await hass.async_block_till_done()

    # Abort on concurrent user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: IP,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

    # Abort on concurrent zeroconf discovery flow
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )
    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_device")
@pytest.mark.usefixtures("mock_zeroconf")
async def test_validate_input(hass: HomeAssistant):
    """Test input validation."""
    info = await config_flow.validate_input(hass, {CONF_IP_ADDRESS: IP})
    assert SERIAL_NUMBER in info
    assert TITLE in info
