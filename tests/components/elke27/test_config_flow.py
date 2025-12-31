"""Test the Elke27 config flow."""

from __future__ import annotations

import builtins
import importlib
import sys
from dataclasses import dataclass
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch

_client_module = ModuleType("elke27_lib.client")


@dataclass(frozen=True, slots=True)
class FakeIdentity:
    """Minimal identity stub."""

    mn: str
    sn: str
    fwver: str
    hwver: str
    osver: str


@dataclass(frozen=True, slots=True)
class FakeLinkKeys:
    """Minimal link keys stub."""

    tempkey_hex: str
    linkkey_hex: str
    linkhmac_hex: str


_client_module.Elke27Client = object
_client_module.Result = object
_client_module.E27Identity = FakeIdentity
_client_module.E27LinkKeys = FakeLinkKeys
_package_module = ModuleType("elke27_lib")
_package_module.client = _client_module
sys.modules.setdefault("elke27_lib", _package_module)
sys.modules.setdefault("elke27_lib.client", _client_module)

from homeassistant import config_entries
from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _client_factory(instances: list[AsyncMock]) -> callable:
    iterator = iter(instances)

    def _factory(*args, **kwargs):
        assert not args
        assert not kwargs
        return next(iterator)

    return _factory


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

    manual_discover_client = AsyncMock()
    manual_discover_client.discover = AsyncMock(
        return_value=FakeResult(ok=True, data=FakeDiscoverResult(panels=[]), error=None)
    )

    link_client = AsyncMock()
    link_client.link = AsyncMock(
        return_value=FakeResult(
            ok=True,
            data={
                "tempkey_hex": "tk",
                "linkkey_hex": "lk",
                "linkhmac_hex": "lh",
            },
            error=None,
        )
    )
    link_client.connect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    link_client.wait_ready = Mock(return_value=True)
    link_client.disconnect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    link_client.panel_info = FakePanelInfo(
        panel_name="Test Panel",
        panel_mac="aa:bb:cc:dd:ee:ff",
        panel_serial="1234",
    )
    link_client.table_info = FakeTableInfo(areas=8, zones=16)

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=_client_factory([discover_client, manual_discover_client, link_client]),
    ), patch(
        "homeassistant.components.elke27.config_flow.async_get_integration_serial",
        AsyncMock(return_value="112233445566"),
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
                "access_code": "1234",
                "passphrase": "test-pass",
            },
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Test Panel"
        assert result2["data"][CONF_HOST] == "192.168.1.10"
        assert result2["data"][CONF_PORT] == DEFAULT_PORT
        assert "link_keys" in result2["data"]
        assert result2["data"][CONF_INTEGRATION_SERIAL] == "112233445566"
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

    link_client = AsyncMock()
    link_client.link = AsyncMock(
        return_value=FakeResult(
            ok=True,
            data={
                "tempkey_hex": "tk",
                "linkkey_hex": "lk",
                "linkhmac_hex": "lh",
            },
            error=None,
        )
    )
    link_client.connect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    link_client.wait_ready = Mock(return_value=True)
    link_client.disconnect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    link_client.panel_info = FakePanelInfo(
        panel_name="Panel A",
        panel_mac="aa:bb:cc:dd:ee:11",
        panel_serial="5678",
    )
    link_client.table_info = FakeTableInfo(areas=2, zones=4)

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=_client_factory([discover_client, link_client]),
    ), patch(
        "homeassistant.components.elke27.config_flow.async_get_integration_serial",
        AsyncMock(return_value="112233445566"),
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
        assert result2["step_id"] == "credentials"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"access_code": "1234", "passphrase": "test-pass"},
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["data"][CONF_HOST] == "192.168.1.20"
        assert result3["data"][CONF_PORT] == DEFAULT_PORT
        assert "link_keys" in result3["data"]
        assert result3["data"][CONF_INTEGRATION_SERIAL] == "112233445566"


async def test_invalid_credentials_returns_error(hass: HomeAssistant) -> None:
    """Test invalid credentials returns a form error."""
    discover_client = AsyncMock()
    discover_client.discover = AsyncMock(
        return_value=FakeResult(ok=True, data=FakeDiscoverResult(panels=[]), error=None)
    )

    manual_discover_client = AsyncMock()
    manual_discover_client.discover = AsyncMock(
        return_value=FakeResult(ok=True, data=FakeDiscoverResult(panels=[]), error=None)
    )

    class InvalidCredentials(Exception):
        """Stub invalid credentials error."""

    link_client = AsyncMock()
    link_client.link = AsyncMock(
        return_value=FakeResult(ok=False, data=None, error=InvalidCredentials())
    )
    link_client.disconnect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=_client_factory([discover_client, manual_discover_client, link_client]),
    ), patch(
        "homeassistant.components.elke27.config_flow.async_get_integration_serial",
        AsyncMock(return_value="112233445566"),
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
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "invalid_credentials"


async def test_relink_updates_entry(hass: HomeAssistant) -> None:
    """Test relink flow updates entry with regenerated link keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Panel",
        data={
            CONF_HOST: "192.168.1.40",
            CONF_PORT: DEFAULT_PORT,
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    link_client = AsyncMock()
    link_client.link = AsyncMock(
        return_value=FakeResult(
            ok=True,
            data={
                "tempkey_hex": "newt",
                "linkkey_hex": "new",
                "linkhmac_hex": "newh",
            },
            error=None,
        )
    )
    link_client.connect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    link_client.wait_ready = Mock(return_value=True)
    link_client.disconnect = AsyncMock(
        return_value=FakeResult(ok=True, data=None, error=None)
    )
    link_client.panel_info = FakePanelInfo(
        panel_name="Panel",
        panel_mac="aa:bb:cc:dd:ee:44",
        panel_serial="9999",
    )
    link_client.table_info = FakeTableInfo(areas=1, zones=1)

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=_client_factory([link_client]),
    ), patch(
        "homeassistant.components.elke27.config_flow.async_get_integration_serial",
        AsyncMock(return_value="112233445566"),
    ), patch(
        "homeassistant.components.elke27.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "relink"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"access_code": "1234", "passphrase": "new-pass"},
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
        assert entry.data["link_keys"]["linkkey_hex"] == "new"
