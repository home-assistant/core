"""Test the Flexit Nordic (BACnet) config flow."""
import asyncio.exceptions
from unittest.mock import patch

from flexit_bacnet import DecodingError
import pytest

from homeassistant import config_entries
from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
async def flow_id(hass: HomeAssistant) -> str:
    """Return initial ID for user-initiaded configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    return result["flow_id"]


@pytest.fixture(autouse=True)
def mock_serial_number():
    """Mock serial number of the device."""
    with patch(
        "homeassistant.components.flexit_bacnet.config_flow.FlexitBACnet.serial_number",
        property(lambda _: "0000-0001"),
    ):
        yield


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.flexit_bacnet.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock


def _patch_update(side_effect=None):
    """Shortcut for mocking device update call (with optional side effects)."""
    return patch(
        "homeassistant.components.flexit_bacnet.config_flow.FlexitBACnet.update",
        side_effect=side_effect,
    )


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
    assert result["title"] == "0000-0001"
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
    assert result2["title"] == "0000-0001"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_DEVICE_ID: 2,
    }
    assert len(mock_setup_entry.mock_calls) == 1


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
    assert result2["title"] == "0000-0001"
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
    assert result2["title"] == "0000-0001"
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
