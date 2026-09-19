"""Tests for the Marantz RS-232 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from marantz_rs232 import MarantzV2007Receiver
import pytest

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_DEVICE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-entry creation tests from setting up the integration."""
    with patch(
        "homeassistant.components.marantz_rs232.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def test_user_form_creates_entry(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test setup needs only the port for a 2007-protocol receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert list(result["data_schema"].schema) == [CONF_DEVICE]
    with patch(
        "homeassistant.components.marantz_rs232.config_flow.MarantzV2007Receiver",
        return_value=mock_receiver,
    ) as constructor:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: MOCK_DEVICE}
        )
    constructor.assert_called_once_with(MOCK_DEVICE)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Marantz receiver"
    assert result["data"] == {CONF_DEVICE: MOCK_DEVICE}
    mock_setup_entry.assert_awaited_once()
    mock_receiver.connect.assert_awaited_once()
    mock_receiver.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ValueError("Invalid port"), "cannot_connect"),
        (ConnectionError("No response"), "cannot_connect"),
        (OSError("Missing device"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
)
async def test_user_form_error_recovers(
    hass: HomeAssistant,
    mock_receiver: MarantzV2007Receiver,
    exception: Exception,
    error: str,
) -> None:
    """Report connection errors and allow retry."""
    mock_receiver.connect.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_DEVICE}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_receiver.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_DEVICE}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_duplicate_port_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Abort if the same port is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_DEVICE}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
