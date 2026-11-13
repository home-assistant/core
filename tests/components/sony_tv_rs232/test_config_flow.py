"""Tests for the Sony TV RS-232 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from sony_tv_rs232 import SerialKitError

from homeassistant.components.sony_tv_rs232.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_PORT
from .conftest import MockSonyTV


@pytest.fixture
def mock_async_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-entry creation tests from setting up the integration."""
    with patch(
        "homeassistant.components.sony_tv_rs232.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_config_flow_tv(mock_sony_tv: MockSonyTV) -> Generator[MagicMock]:
    """Hand the config flow the mock TV."""
    with patch(
        "homeassistant.components.sony_tv_rs232.config_flow.SonyTV",
        return_value=mock_sony_tv,
    ) as mock_tv_class:
        yield mock_tv_class


async def test_user_form_creates_entry(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    mock_config_flow_tv: MagicMock,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sony TV"
    assert result["data"] == {CONF_PORT: MOCK_PORT}
    mock_async_setup_entry.assert_awaited_once()
    # Only the port is checked: the full attribute round is skipped.
    assert mock_config_flow_tv.call_args == call(MOCK_PORT, refresh_on_connect=False)
    mock_sony_tv.connect.assert_awaited_once()
    mock_sony_tv.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ValueError("Invalid port"), "cannot_connect"),
        (OSError("No such device"), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (SerialKitError("link lost during handshake"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_form_error_then_recovers(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    mock_async_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test a failed connection keeps the user on the form, then recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_sony_tv.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    mock_sony_tv.disconnect.assert_not_awaited()

    mock_sony_tv.connect.side_effect = mock_sony_tv._mock_connect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PORT: MOCK_PORT}


async def test_user_duplicate_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if the same port is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_duplicate_added_while_connecting_aborts(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    mock_async_setup_entry: AsyncMock,
) -> None:
    """Test we abort if the port was configured while the flow was connecting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    async def _connect_while_other_flow_finishes() -> None:
        MockConfigEntry(domain=DOMAIN, data={CONF_PORT: MOCK_PORT}).add_to_hass(hass)

    mock_sony_tv.connect.side_effect = _connect_while_other_flow_finishes

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_async_setup_entry.assert_not_awaited()


async def test_esphome_api_key_not_logged(
    hass: HomeAssistant,
    mock_sony_tv: MockSonyTV,
    mock_async_setup_entry: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected error logs the ESPHome proxy port without its query."""
    port = "esphome://tv-proxy.local/?port_name=TTL&key=secret-api-key"
    mock_sony_tv.connect.side_effect = RuntimeError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: port}
    )

    assert result["errors"] == {"base": "unknown"}
    assert "esphome://tv-proxy.local/" in caplog.text
    assert "secret-api-key" not in caplog.text

    mock_sony_tv.connect.side_effect = mock_sony_tv._mock_connect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: port}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PORT: port}
