"""Tests for the EARN-E P1 Meter config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from earn_e_p1 import EarnEP1Device
import pytest

from homeassistant import config_entries
from homeassistant.components.earn_e_p1.const import CONF_SERIAL
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DOMAIN, MOCK_HOST, MOCK_SERIAL

from tests.common import MockConfigEntry

DISCOVER_PATH = "homeassistant.components.earn_e_p1.config_flow.discover"
VALIDATE_PATH = "homeassistant.components.earn_e_p1.config_flow.validate"


def _mock_device(
    host: str = MOCK_HOST, serial: str | None = MOCK_SERIAL
) -> EarnEP1Device:
    """Create a mock EarnEP1Device."""
    return EarnEP1Device(host=host, serial=serial)


async def test_user_flow_discovery_succeeds(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow when auto-discovery finds a device with serial."""
    with patch(DISCOVER_PATH, return_value=[_mock_device()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"EARN-E P1 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_SERIAL


async def test_user_flow_discovery_no_serial_validates(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery without serial triggers validation on confirm."""
    with patch(DISCOVER_PATH, return_value=[_mock_device(serial=None)]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SERIAL] == MOCK_SERIAL


async def test_user_flow_discovery_no_serial_validate_fails(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery without serial aborts when validation also fails."""
    with patch(DISCOVER_PATH, return_value=[_mock_device(serial=None)]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_discovery_no_serial_oserror(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery without serial aborts on OSError during validation."""
    with patch(DISCOVER_PATH, return_value=[_mock_device(serial=None)]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_discovery_no_serial_unexpected_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery without serial aborts on unexpected error during validation."""
    with patch(DISCOVER_PATH, return_value=[_mock_device(serial=None)]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=RuntimeError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_user_flow_discovery_timeout_shows_manual_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow falls back to manual form when discovery times out, then recovers."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"EARN-E P1 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL}


async def test_manual_entry_validation_timeout_then_retry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual entry: validation timeout shows error, retry succeeds."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (OSError("Address in use"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_manual_entry_validation_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test manual entry: errors during validation show correct error, retry succeeds."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_entry_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test manual entry aborts when device is already configured."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_confirm_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discovery confirm aborts when device is already configured."""
    with patch(DISCOVER_PATH, return_value=[_mock_device()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discover_uses_shared_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test _async_discover uses shared listener when available."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_listener.discover = AsyncMock(
        return_value=[_mock_device(host="192.168.1.200", serial="E9999999999999999")]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    mock_listener.discover.assert_called_once()


async def test_discover_without_shared_listener(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test _async_discover uses library discover when no shared listener."""
    with patch(DISCOVER_PATH, return_value=[_mock_device()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_discover_without_shared_listener_oserror(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test _async_discover falls back to manual form on OSError, then succeeds."""
    with patch(DISCOVER_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_validate_uses_shared_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test _async_validate_host uses shared listener when available."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    other_host = "192.168.1.200"
    other_serial = "E9999999999999999"
    mock_listener.discover = AsyncMock(return_value=[])
    mock_listener.validate = AsyncMock(
        return_value=_mock_device(host=other_host, serial=other_serial)
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: other_host}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_listener.validate.assert_called_once()


async def test_validate_without_shared_listener(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test _async_validate_host uses library validate when no shared listener."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["step_id"] == "user"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
