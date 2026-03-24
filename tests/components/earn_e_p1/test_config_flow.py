"""Tests for the EARN-E P1 Meter config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from earn_e_p1 import EarnEP1Device

from homeassistant import config_entries
from homeassistant.components.earn_e_p1.const import CONF_SERIAL
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DOMAIN, MOCK_HOST, MOCK_SERIAL

from tests.common import MockConfigEntry

DISCOVER_PATH = (
    "homeassistant.components.earn_e_p1.config_flow.EarnEP1ConfigFlow._async_discover"
)
VALIDATE_PATH = (
    "homeassistant.components.earn_e_p1.config_flow"
    ".EarnEP1ConfigFlow._async_validate_host"
)


def _mock_device(
    host: str = MOCK_HOST, serial: str | None = MOCK_SERIAL
) -> EarnEP1Device:
    """Create a mock EarnEP1Device."""
    return EarnEP1Device(host=host, serial=serial)


async def test_user_flow_discovery_succeeds(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow when auto-discovery finds a device with serial."""
    with patch(DISCOVER_PATH, return_value=_mock_device()):
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
    with patch(DISCOVER_PATH, return_value=_mock_device(serial=None)):
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
    with patch(DISCOVER_PATH, return_value=_mock_device(serial=None)):
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
    with patch(DISCOVER_PATH, return_value=_mock_device(serial=None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_discovery_timeout_shows_manual_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow falls back to manual form when discovery times out."""
    with patch(DISCOVER_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_manual_entry_validation_succeeds(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual IP entry with successful validation."""
    with patch(DISCOVER_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["step_id"] == "user"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"EARN-E P1 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_SERIAL


async def test_manual_entry_validation_timeout_then_retry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual entry: validation timeout shows error, retry succeeds."""
    with patch(DISCOVER_PATH, return_value=None):
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


async def test_manual_entry_validation_oserror(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual entry: OSError during validation shows cannot_connect."""
    with patch(DISCOVER_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_entry_unexpected_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual entry: unexpected exception shows unknown error."""
    with patch(DISCOVER_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=RuntimeError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_manual_entry_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual entry aborts when device is already configured."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title=f"EARN-E P1 ({MOCK_HOST})",
        data={CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL},
        unique_id=MOCK_SERIAL,
    )
    existing.add_to_hass(hass)

    with patch(DISCOVER_PATH, return_value=None):
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
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery confirm aborts when device is already configured."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title=f"EARN-E P1 ({MOCK_HOST})",
        data={CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL},
        unique_id=MOCK_SERIAL,
    )
    existing.add_to_hass(hass)

    with patch(DISCOVER_PATH, return_value=_mock_device()):
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
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_listener: MagicMock
) -> None:
    """Test _async_discover uses shared listener when available."""
    mock_listener.discover = AsyncMock(return_value=[_mock_device()])
    hass.data[DOMAIN] = mock_listener

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
    with patch(
        "homeassistant.components.earn_e_p1.config_flow.discover",
        return_value=[_mock_device()],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_discover_without_shared_listener_oserror(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test _async_discover returns None on OSError when no shared listener."""
    with patch(
        "homeassistant.components.earn_e_p1.config_flow.discover",
        side_effect=OSError("Address in use"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_validate_uses_shared_listener(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_listener: MagicMock
) -> None:
    """Test _async_validate_host uses shared listener when available."""
    mock_listener.discover = AsyncMock(return_value=[])
    mock_listener.validate = AsyncMock(return_value=_mock_device())
    hass.data[DOMAIN] = mock_listener

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_listener.validate.assert_called_once()


async def test_validate_without_shared_listener(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test _async_validate_host uses library validate when no shared listener."""
    with patch(
        "homeassistant.components.earn_e_p1.config_flow.discover",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.earn_e_p1.config_flow.validate",
        return_value=_mock_device(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
