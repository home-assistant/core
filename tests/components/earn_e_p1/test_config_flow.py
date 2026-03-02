"""Tests for the EARN-E P1 Meter config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.earn_e_p1.config_flow import DeviceInfo
from homeassistant.components.earn_e_p1.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_SERIAL

from tests.common import MockConfigEntry

LISTEN_PATH = (
    "homeassistant.components.earn_e_p1.config_flow.EarnEP1ConfigFlow"
    "._async_listen_for_device"
)


async def test_user_flow_discovery_succeeds(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test user flow when auto-discovery finds a device."""
    with patch(LISTEN_PATH, return_value=DeviceInfo(host=MOCK_HOST, serial=MOCK_SERIAL)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Confirm discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"EARN-E P1 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST, "serial": MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_SERIAL


async def test_user_flow_discovery_timeout_shows_manual_form(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test user flow falls back to manual form when discovery times out."""
    with patch(LISTEN_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow_discovery_oserror_shows_manual_form(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test user flow falls back to manual form when discovery gets OSError."""
    with patch(LISTEN_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_manual_entry_validation_succeeds(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test manual IP entry with successful validation."""
    with patch(LISTEN_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        LISTEN_PATH, return_value=DeviceInfo(host=MOCK_HOST, serial=MOCK_SERIAL)
    ):
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
    with patch(LISTEN_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    # First attempt times out
    with patch(LISTEN_PATH, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Retry succeeds
    with patch(
        LISTEN_PATH, return_value=DeviceInfo(host=MOCK_HOST, serial=MOCK_SERIAL)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_entry_validation_oserror(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test manual entry: OSError during validation shows cannot_connect."""
    with patch(LISTEN_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(LISTEN_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_entry_unexpected_error(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test manual entry: unexpected exception shows unknown error."""
    with patch(LISTEN_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(LISTEN_PATH, side_effect=RuntimeError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_manual_entry_no_serial_uses_host_as_unique_id(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test manual entry when device has no serial uses host as unique_id."""
    with patch(LISTEN_PATH, return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(LISTEN_PATH, return_value=DeviceInfo(host=MOCK_HOST, serial=None)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: MOCK_HOST, "serial": None}
    assert result["result"].unique_id == MOCK_HOST


async def test_single_config_entry_abort(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test that a second config entry is blocked (single_config_entry)."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Existing",
        data={CONF_HOST: "192.168.1.50", "serial": MOCK_SERIAL},
        unique_id=MOCK_SERIAL,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_succeeds(
    hass: HomeAssistant, mock_config_entry, mock_setup_entry
) -> None:
    """Test reconfigure flow with new IP."""
    new_host = "192.168.1.200"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        LISTEN_PATH,
        return_value=DeviceInfo(host=new_host, serial=MOCK_SERIAL),
    ):
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
    """Test reconfigure when port is in use (coordinator running) skips validation."""
    new_host = "192.168.1.200"

    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(LISTEN_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: new_host}
        )

    # Should succeed despite OSError — falls back to skip validation
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == new_host
    assert mock_config_entry.data["serial"] == MOCK_SERIAL


async def test_reconfigure_unexpected_error(
    hass: HomeAssistant, mock_config_entry, mock_setup_entry
) -> None:
    """Test reconfigure with unexpected error shows unknown error."""
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(LISTEN_PATH, side_effect=RuntimeError("boom")):
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

    with patch(
        LISTEN_PATH,
        return_value=DeviceInfo(host=other_host, serial=other_serial),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: other_host}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_no_serial_uses_host(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test discovery flow when device has no serial uses host as unique_id."""
    with patch(LISTEN_PATH, return_value=DeviceInfo(host=MOCK_HOST, serial=None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_HOST
