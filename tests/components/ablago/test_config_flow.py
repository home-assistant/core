"""Tests for the Ablago config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from ablago import AblagoAuthError, AblagoConnectionError, AblagoError, AblagoSSLError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ablago.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import API_KEY, URL, USER_INPUT

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


# The reauth form only asks for the key, so every error is shown for the form.
REAUTH_ERRORS = [
    pytest.param(
        AblagoAuthError("401", status=401), {"base": "invalid_auth"}, id="auth"
    ),
    pytest.param(AblagoSSLError("certificate"), {"base": "ssl_error"}, id="ssl"),
    pytest.param(
        AblagoConnectionError("gone"), {"base": "cannot_connect"}, id="connection"
    ),
    pytest.param(
        AblagoError("redirect", status=301), {"base": "redirect"}, id="redirect"
    ),
    pytest.param(
        AblagoError("HTTP 404", status=404), {"base": "not_ablago"}, id="not_found"
    ),
    pytest.param(AblagoError("broken"), {"base": "not_ablago"}, id="no_status"),
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


@pytest.mark.usefixtures("mock_ablago_client")
async def test_user_flow_invalid_url(hass: HomeAssistant) -> None:
    """Test an address without http:// or https:// is rejected."""
    flow_id = await _start_user_flow(hass)
    with patch(
        "homeassistant.components.ablago.coordinator.AblagoClient",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {**USER_INPUT, CONF_URL: "ablago.example.org"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}

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


@pytest.mark.usefixtures("mock_ablago_client")
async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a new key replaces the old one."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "dms_new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**USER_INPUT, CONF_API_KEY: "dms_new"}


@pytest.mark.parametrize(("side_effect", "errors"), REAUTH_ERRORS)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    errors: dict[str, str],
) -> None:
    """Test a key that does not work is not saved."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    mock_ablago_client.zaehler.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "dms_new"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    assert mock_config_entry.data[CONF_API_KEY] == API_KEY

    mock_ablago_client.zaehler.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "dms_new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_ablago_client")
async def test_reauth_to_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a reauth cannot turn an entry into a copy of another one."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, data={**USER_INPUT, CONF_API_KEY: "dms_counters_jonas"}
    )
    other.add_to_hass(hass)
    result = await other.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert other.data[CONF_API_KEY] == "dms_counters_jonas"


@pytest.mark.usefixtures("mock_ablago_client")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test address, key and certificate check can be changed."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new = {
        CONF_URL: "http://192.168.1.20:3000",
        CONF_API_KEY: "dms_new",
        CONF_VERIFY_SSL: False,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == new


@pytest.mark.parametrize(("side_effect", "errors"), ERRORS)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_ablago_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    errors: dict[str, str],
) -> None:
    """Test a change that does not work is not saved."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    mock_ablago_client.zaehler.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    mock_ablago_client.zaehler.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_ablago_client")
async def test_reconfigure_to_existing_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an entry cannot be changed into a copy of another one."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, data={**USER_INPUT, CONF_API_KEY: "dms_counters_jonas"}
    )
    other.add_to_hass(hass)
    result = await other.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
