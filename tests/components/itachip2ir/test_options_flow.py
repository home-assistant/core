"""Tests for the iTach IP2IR options flow."""

from unittest.mock import AsyncMock, MagicMock

from pyitach import ItachConnectionError, ItachError
import pytest

from homeassistant.components.itachip2ir.const import DOMAIN
from homeassistant.components.itachip2ir.options_flow import (
    CONF_LAST_PORT_REFRESH,
    SOURCE_REFRESH_INFRARED_PORTS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _entry(
    *,
    options: dict[str, object] | None = None,
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        data={
            "host": "192.168.1.50",
            "port": 4998,
            "device_id": "000C1E123456",
        },
        options=options or {},
        source="user",
        entry_id="test-entry",
        unique_id="000c1e123456",
    )


async def test_options_flow_menu(hass: HomeAssistant) -> None:
    """Test the options menu."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == [SOURCE_REFRESH_INFRARED_PORTS]


async def test_options_flow_refresh_form_from_source(
    hass: HomeAssistant,
) -> None:
    """Test refresh source opens the refresh confirmation form directly."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_REFRESH_INFRARED_PORTS
    assert result["errors"] == {}


async def test_options_flow_refresh_success(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful infrared refresh."""
    entry = _entry()
    entry.add_to_hass(hass)

    capability = MagicMock()
    capability.enabled_ports = [1, 2, 3]

    client = MagicMock()
    client.close = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.ItachClient",
        MagicMock(return_value=client),
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.async_get_ir_capability",
        AsyncMock(return_value=capability),
    )

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_LAST_PORT_REFRESH in result["data"]
    client.close.assert_awaited_once()


async def test_options_flow_refresh_preserves_existing_options(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test refresh preserves unrelated options."""
    entry = _entry(options={"custom_option": "keep-me"})
    entry.add_to_hass(hass)

    capability = MagicMock()
    capability.enabled_ports = [1]

    client = MagicMock()
    client.close = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.ItachClient",
        MagicMock(return_value=client),
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.async_get_ir_capability",
        AsyncMock(return_value=capability),
    )

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["custom_option"] == "keep-me"
    assert CONF_LAST_PORT_REFRESH in result["data"]
    client.close.assert_awaited_once()


async def test_options_flow_refresh_uses_host_and_port_from_options(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test refresh uses host and port overrides from options."""
    entry = _entry(options={"host": "192.168.1.60", "port": 1234})
    entry.add_to_hass(hass)

    capability = MagicMock()
    capability.enabled_ports = [1]

    client = MagicMock()
    client.close = AsyncMock()
    client_factory = MagicMock(return_value=client)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.ItachClient",
        client_factory,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.async_get_ir_capability",
        AsyncMock(return_value=capability),
    )

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    client_factory.assert_called_once_with("192.168.1.60", 1234)
    client.close.assert_awaited_once()


async def test_options_flow_refresh_empty_enabled_ports_reports_no_ir_ports(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test refresh reports no_ir_ports when no ports are enabled."""
    entry = _entry()
    entry.add_to_hass(hass)

    capability = MagicMock()
    capability.enabled_ports = []

    client = MagicMock()
    client.close = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.ItachClient",
        MagicMock(return_value=client),
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.async_get_ir_capability",
        AsyncMock(return_value=capability),
    )

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_ir_ports"}
    client.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (ItachConnectionError("offline"), "cannot_connect"),
        (ItachError("bad response"), "unknown"),
        (ValueError("no ports"), "no_ir_ports"),
    ],
)
async def test_options_flow_refresh_errors(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_error: str,
) -> None:
    """Test refresh validation errors are reported on the form."""
    entry = _entry()
    entry.add_to_hass(hass)

    client = MagicMock()
    client.close = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.ItachClient",
        MagicMock(return_value=client),
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.async_get_ir_capability",
        AsyncMock(side_effect=error),
    )

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    client.close.assert_awaited_once()
