"""Test the Flexit Nordic (BACnet) config flow."""
import asyncio.exceptions

from flexit_bacnet import DecodingError
import pytest

from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(
    hass: HomeAssistant, flow_id: str, mock_setup_entry, mock_flexit_bacnet
) -> None:
    """Test we get the form and the happy path works."""
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_DEVICE_ID: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Device Name"
    assert result["context"]["unique_id"] == "0000-0001"
    assert result["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_DEVICE_ID: 2,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_flexit_bacnet.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            asyncio.exceptions.TimeoutError,
            "cannot_connect",
        ),
        (ConnectionError, "cannot_connect"),
        (DecodingError, "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant,
    flow_id: str,
    error: Exception,
    message: str,
    mock_setup_entry,
    mock_flexit_bacnet,
) -> None:
    """Test that we return 'cannot_connect' error when attempting to connect to an incorrect IP address.

    The flexit_bacnet library raises asyncio.exceptions.TimeoutError in that scenario.
    """
    mock_flexit_bacnet.update.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_DEVICE_ID: 2,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": message}
    assert len(mock_setup_entry.mock_calls) == 0

    # ensure that user can recover from this error
    mock_flexit_bacnet.update.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_DEVICE_ID: 2,
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Device Name"
    assert result2["context"]["unique_id"] == "0000-0001"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_DEVICE_ID: 2,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_device_already_exist(
    hass: HomeAssistant, flow_id: str, mock_flexit_bacnet, mock_config_entry
) -> None:
    """Test that we cannot add already added device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_DEVICE_ID: 2,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
