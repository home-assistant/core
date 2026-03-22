"""Tests for the EARN-E P1 Meter config flow."""

from __future__ import annotations

from unittest.mock import patch

from earn_e_p1 import EarnEP1Device
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.earn_e_p1.const import DOMAIN

from .conftest import MOCK_HOST, MOCK_SERIAL

DISCOVER_PATH = (
    "custom_components.earn_e_p1.config_flow.EarnEP1ConfigFlow._async_discover"
)
VALIDATE_PATH = (
    "custom_components.earn_e_p1.config_flow.EarnEP1ConfigFlow._async_validate_host"
)


def _mock_device(
    host: str = MOCK_HOST, serial: str | None = MOCK_SERIAL
) -> EarnEP1Device:
    """Create a mock EarnEP1Device."""
    return EarnEP1Device(host=host, serial=serial)


async def test_user_flow_discovery_succeeds(
    hass: HomeAssistant, mock_setup_entry
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
    assert result["data"] == {CONF_HOST: MOCK_HOST, "serial": MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_SERIAL


async def test_user_flow_discovery_no_serial_validates(
    hass: HomeAssistant, mock_setup_entry
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
    assert result["data"]["serial"] == MOCK_SERIAL


async def test_user_flow_discovery_no_serial_validate_fails(
    hass: HomeAssistant, mock_setup_entry
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


async def test_user_flow_discovery_timeout_shows_manual_form(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test user flow falls back to manual form when discovery times out."""
    with patch(DISCOVER_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_manual_entry_validation_succeeds(
    hass: HomeAssistant, mock_setup_entry
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
    assert result["data"] == {CONF_HOST: MOCK_HOST, "serial": MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_SERIAL


async def test_manual_entry_validation_timeout_then_retry(
    hass: HomeAssistant, mock_setup_entry
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
    hass: HomeAssistant, mock_setup_entry
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
    hass: HomeAssistant, mock_setup_entry
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



async def test_reconfigure_succeeds(
    hass: HomeAssistant, mock_config_entry, mock_setup_entry
) -> None:
    """Test reconfigure flow with new IP."""
    new_host = "192.168.1.200"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(VALIDATE_PATH, return_value=_mock_device(host=new_host)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: new_host}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == new_host
    assert mock_config_entry.data["serial"] == MOCK_SERIAL


async def test_reconfigure_port_in_use_skips_validation(
    hass: HomeAssistant, mock_config_entry, mock_setup_entry
) -> None:
    """Test reconfigure when port is in use preserves existing serial."""
    new_host = "192.168.1.200"

    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(VALIDATE_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: new_host}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == new_host
    assert mock_config_entry.data["serial"] == MOCK_SERIAL


async def test_reconfigure_unexpected_error(
    hass: HomeAssistant, mock_config_entry, mock_setup_entry
) -> None:
    """Test reconfigure with unexpected error shows unknown error."""
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(VALIDATE_PATH, side_effect=RuntimeError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "unknown"}


async def test_reconfigure_duplicate_abort(
    hass: HomeAssistant, mock_config_entry, mock_setup_entry
) -> None:
    """Test reconfigure aborts when new IP matches existing entry."""
    other_host = "192.168.1.50"
    other_serial = "E0099999999999999"

    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        data={CONF_HOST: other_host, "serial": other_serial},
        unique_id=other_serial,
    )
    other_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(VALIDATE_PATH, return_value=_mock_device(host=other_host, serial=other_serial)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: other_host}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
