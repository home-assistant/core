"""Test the Elke27 config flow."""

from __future__ import annotations

import builtins
import importlib
import sys
from dataclasses import dataclass
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch

from homeassistant import config_entries
from homeassistant.components.elke27.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


_client_module = ModuleType("elke27_lib.client")
_client_module.Elke27Client = object
_client_module.Result = object
_package_module = ModuleType("elke27_lib")
_package_module.client = _client_module
sys.modules.setdefault("elke27_lib", _package_module)
sys.modules.setdefault("elke27_lib.client", _client_module)


@dataclass
class FakeDiscoverResult:
    """Minimal discover result stub."""

    panels: list[object]


@dataclass
class FakeResult:
    """Minimal Result stub."""

    ok: bool
    data: object | None
    error: object | None


@dataclass
class FakePanel:
    """Discovered panel stub."""

    panel_mac: str
    panel_name: str
    panel_serial: str
    panel_host: str
    port: int
    tls_port: int | None = None


@dataclass
class FakePanelInfo:
    """Panel info snapshot stub."""

    panel_name: str
    panel_mac: str
    panel_serial: str


@dataclass
class FakeTableInfo:
    """Table info snapshot stub."""

    areas: int
    zones: int


def test_imports_without_elkm1_lib(monkeypatch) -> None:
    """Test that Elke27 imports do not require elkm1_lib."""
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("elkm1_lib"):
            raise AssertionError("elkm1_lib import attempted")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.import_module("homeassistant.components.elke27")
    importlib.import_module("homeassistant.components.elke27.config_flow")


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test manual host entry creates an entry."""
    discover_client = AsyncMock()
    discover_client.discover = AsyncMock(
        return_value=FakeResult(ok=True, data=FakeDiscoverResult(panels=[]), error=None)
    )

    connect_client = AsyncMock()
    connect_client.connect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    connect_client.wait_ready = Mock(return_value=True)
    connect_client.disconnect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    connect_client.panel_info = FakePanelInfo(
        panel_name="Test Panel",
        panel_mac="aa:bb:cc:dd:ee:ff",
        panel_serial="1234",
    )
    connect_client.table_info = FakeTableInfo(areas=8, zones=16)

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=[discover_client, connect_client],
    ), patch(
        "homeassistant.components.elke27.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.10",
                CONF_PORT: DEFAULT_PORT,
            },
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Test Panel"
        assert result2["data"][CONF_HOST] == "192.168.1.10"
        assert result2["data"][CONF_PORT] == DEFAULT_PORT
        assert "panel_info" in result2["options"]
        assert "table_info" in result2["options"]


async def test_discovery_selection_creates_entry(hass: HomeAssistant) -> None:
    """Test discovery selection path creates an entry."""
    panel = FakePanel(
        panel_mac="aa:bb:cc:dd:ee:11",
        panel_name="Panel A",
        panel_serial="5678",
        panel_host="192.168.1.20",
        port=DEFAULT_PORT,
    )
    discover_client = AsyncMock()
    discover_client.discover = AsyncMock(
        return_value=FakeResult(
            ok=True, data=FakeDiscoverResult(panels=[panel]), error=None
        )
    )

    connect_client = AsyncMock()
    connect_client.connect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    connect_client.wait_ready = Mock(return_value=True)
    connect_client.disconnect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    connect_client.panel_info = FakePanelInfo(
        panel_name="Panel A",
        panel_mac="aa:bb:cc:dd:ee:11",
        panel_serial="5678",
    )
    connect_client.table_info = FakeTableInfo(areas=2, zones=4)

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=[discover_client, connect_client],
    ), patch(
        "homeassistant.components.elke27.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": panel.panel_mac},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "link"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["data"][CONF_HOST] == "192.168.1.20"
        assert result3["data"][CONF_PORT] == DEFAULT_PORT


async def test_manual_entry_handles_invalid_link_keys(hass: HomeAssistant) -> None:
    """Test invalid link keys returns a form error."""
    discover_client = AsyncMock()
    discover_client.discover = AsyncMock(
        return_value=FakeResult(ok=True, data=FakeDiscoverResult(panels=[]), error=None)
    )

    connect_client = AsyncMock()
    connect_client.connect = AsyncMock(
        return_value=FakeResult(ok=False, data=None, error=RuntimeError("bad keys"))
    )
    connect_client.disconnect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=[discover_client, connect_client],
    ), patch(
        "homeassistant.components.elke27.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "manual"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.30",
                CONF_PORT: DEFAULT_PORT,
                "link_keys": "{bad json",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "invalid_link_keys"
