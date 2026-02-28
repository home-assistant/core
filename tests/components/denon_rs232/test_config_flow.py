"""Tests for the Denon RS232 config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.denon_rs232.const import CONF_MODEL, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_PORT = "/dev/ttyUSB0"
MOCK_MODEL = "avr_3805"


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we show the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_form_creates_entry(hass: HomeAssistant) -> None:
    """Test successful config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_receiver = AsyncMock()
    mock_receiver.connect = AsyncMock()
    mock_receiver.disconnect = AsyncMock()

    with patch(
        "homeassistant.components.denon_rs232.config_flow.DenonReceiver",
        return_value=mock_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Denon AVR-3805 / AVC-3890 ({MOCK_PORT})"
    assert result["data"] == {CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL}
    mock_receiver.connect.assert_awaited_once()
    mock_receiver.disconnect.assert_awaited_once()


async def test_user_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_receiver = AsyncMock()
    mock_receiver.connect = AsyncMock(side_effect=ConnectionError("No response"))

    with patch(
        "homeassistant.components.denon_rs232.config_flow.DenonReceiver",
        return_value=mock_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form_os_error(hass: HomeAssistant) -> None:
    """Test we handle OS errors (e.g. serial port not found)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_receiver = AsyncMock()
    mock_receiver.connect = AsyncMock(side_effect=OSError("No such device"))

    with patch(
        "homeassistant.components.denon_rs232.config_flow.DenonReceiver",
        return_value=mock_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_receiver = AsyncMock()
    mock_receiver.connect = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "homeassistant.components.denon_rs232.config_flow.DenonReceiver",
        return_value=mock_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_duplicate_port_aborts(hass: HomeAssistant) -> None:
    """Test we abort if the same port is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
