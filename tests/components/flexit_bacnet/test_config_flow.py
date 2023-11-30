"""Test the Flexit Nordic (BACnet) config flow."""
import asyncio.exceptions

from flexit_bacnet import DecodingError

from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from ...common import MockConfigEntry
from .conftest import _patch_update


async def test_form(hass: HomeAssistant, flow_id: str, mock_setup_entry) -> None:
    """Test we get the form and the happy path works."""
    with _patch_update():
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


async def test_form_invalid_device(
    hass: HomeAssistant, flow_id: str, mock_setup_entry
) -> None:
    """Test that we return 'cannot_connect' error when attempting to connect to an incorrect IP address.

    The flexit_bacnet library raises asyncio.exceptions.TimeoutError in that scenario.
    """
    with _patch_update(side_effect=asyncio.exceptions.TimeoutError):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_DEVICE_ID: 2,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0

    # ensure that user can recover from this error
    with _patch_update():
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


async def test_form_device_already_exist(hass: HomeAssistant, flow_id: str) -> None:
    """Test that we cannot add already added device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_DEVICE_ID: 2,
        },
        unique_id="0000-0001",
    )
    entry.add_to_hass(hass)
    with _patch_update():
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


async def test_form_connection_error(
    hass: HomeAssistant, flow_id: str, mock_setup_entry
) -> None:
    """Test that we return 'cannot_connect' error when ConnectionError happens.

    The flexit_bacnet library raises ConnectionError in case of connectivity issues.
    """
    with _patch_update(side_effect=ConnectionError):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_DEVICE_ID: 2,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # ensure that user can recover from this error
    with _patch_update():
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


async def test_form_decoding_error(
    hass: HomeAssistant, flow_id: str, mock_setup_entry
) -> None:
    """Test that we return 'cannot_connect' error when DecodingError happens.

    The flexit_bacnet library raises DecodingError when it receives invalid response from a BACnet peer.
    """
    with _patch_update(side_effect=DecodingError):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_DEVICE_ID: 2,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # ensure that user can recover from this error
    with _patch_update():
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


async def test_form_unexpected_error(hass: HomeAssistant, flow_id: str) -> None:
    """Test we handle unexpected errors."""
    with _patch_update(side_effect=Exception):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_DEVICE_ID: 2,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
