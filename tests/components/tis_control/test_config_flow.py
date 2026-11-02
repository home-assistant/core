"""Test the TIS Control config flow."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from tis_smartbus import TISConnectionError

from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: 6000}


async def _submit(hass: HomeAssistant, user_input: dict[str, Any]) -> Any:
    """Open the user step and submit it, as a person would."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_user_flow(hass: HomeAssistant, mock_gateway: MagicMock) -> None:
    """Test the full user flow finds the dimmer channels."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"TIS gateway {HOST}"
    assert result["result"].unique_id == f"{HOST}:6000"
    devices = result["data"][CONF_DEVICES]
    # The HVAC module is not a light; the dimmer reports its own six channels.
    assert [d["channel"] for d in devices] == [1, 2, 3, 4, 5, 6]
    assert devices[0] == {
        "subnet": 1,
        "device": 5,
        "channel": 1,
        "module": "Living Dimmer",
        "model": "DIM-6CH-2A",
    }
    mock_gateway.close.assert_awaited_once()


async def test_channel_count_falls_back_to_device_table(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """A dimmer that does not answer the status read gets its count from the table."""
    mock_gateway.read_channels.side_effect = None
    mock_gateway.read_channels.return_value = None
    mock_gateway.discover.return_value[0].name = ""
    result = await _submit(hass, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{HOST}:6000"
    devices = result["data"][CONF_DEVICES]
    assert len(devices) == 6
    assert devices[0]["module"] == "DIM-6CH-2A 1.5"


@pytest.mark.parametrize(
    ("side_effect", "discovered", "error"),
    [
        (TISConnectionError("port busy"), None, "cannot_connect"),
        (RuntimeError("boom"), None, "unknown"),
        (None, [], "no_devices"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    side_effect: Exception | None,
    discovered: list | None,
    error: str,
) -> None:
    """Test errors are shown and the flow recovers."""
    original = mock_gateway.discover.return_value
    mock_gateway.connect.side_effect = side_effect
    if discovered is not None:
        mock_gateway.discover.return_value = discovered
    result = await _submit(hass, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_gateway.connect.side_effect = None
    mock_gateway.discover.return_value = original
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{HOST}:6000"


async def test_already_configured(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same gateway cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await _submit(hass, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_second_gateway_of_same_site(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Another gateway of an already configured site finds the same modules: abort."""
    mock_config_entry.add_to_hass(hass)
    result = await _submit(hass, {CONF_HOST: "192.168.1.51", CONF_PORT: 6000})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
