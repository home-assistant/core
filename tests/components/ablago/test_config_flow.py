"""Tests for the Ablago config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from ablago import AblagoAuthError, AblagoConnectionError, AblagoError, AblagoSSLError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ablago.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import URL, USER_INPUT

ERRORS = [
    pytest.param(
        AblagoAuthError("401", status=401), {"base": "invalid_auth"}, id="auth"
    ),
    pytest.param(AblagoSSLError("certificate"), {CONF_URL: "ssl_error"}, id="ssl"),
    pytest.param(
        AblagoConnectionError("gone"), {CONF_URL: "cannot_connect"}, id="connection"
    ),
    pytest.param(
        AblagoError("redirect", status=301), {CONF_URL: "redirect"}, id="redirect"
    ),
    pytest.param(
        AblagoError("HTTP 404", status=404), {CONF_URL: "not_ablago"}, id="not_found"
    ),
    pytest.param(AblagoError("broken"), {CONF_URL: "not_ablago"}, id="no_status"),
    pytest.param(RuntimeError("boom"), {"base": "unknown"}, id="unknown"),
]


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Do not set up the entry after the flow."""
    with patch(
        "homeassistant.components.ablago.async_setup_entry", return_value=None
    ) as setup:
        yield setup


async def _start_user_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result["flow_id"]


@pytest.mark.usefixtures("mock_ablago_client")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the entry is named after the host and the address is normalized."""
    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_URL: f"  {URL}/ "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ablago.example.org"
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(("side_effect", "errors"), ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    side_effect: Exception,
    errors: dict[str, str],
) -> None:
    """Test every failure shows its own message and the flow recovers."""
    flow_id = await _start_user_flow(hass)
    mock_ablago_client.zaehler.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    mock_ablago_client.zaehler.side_effect = None
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_url(
    hass: HomeAssistant, mock_ablago_client_class: MagicMock
) -> None:
    """Test an address without http:// or https:// is rejected."""
    flow_id = await _start_user_flow(hass)
    mock_ablago_client_class.side_effect = ValueError
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_URL: "ablago.example.org"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}

    mock_ablago_client_class.side_effect = None
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_ablago_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same address and key cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_ablago_client")
async def test_second_person(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test another key for the same Ablago gets its own entry."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_API_KEY: "dms_counters_jonas"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
