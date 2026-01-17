"""Test the Elke27 config flow."""

from __future__ import annotations

import builtins
import importlib
import json
import sys
from dataclasses import dataclass
from types import ModuleType
from unittest.mock import AsyncMock, patch

_elke27_lib = ModuleType("elke27_lib")
_elke27_lib_errors = ModuleType("elke27_lib.errors")
_elke27_lib_client = ModuleType("elke27_lib.client")


class Elke27Error(Exception):
    """Base Elke27 error."""


class Elke27AuthError(Elke27Error):
    """Auth error stub."""


class Elke27LinkRequiredError(Elke27Error):
    """Link required stub."""


class Elke27TimeoutError(Elke27Error):
    """Timeout stub."""


class Elke27ConnectionError(Elke27Error):
    """Connection stub."""


class Elke27DisconnectedError(Elke27Error):
    """Disconnected stub."""


class AuthorizationRequired(Elke27Error):
    """Authorization required stub."""


class Elke27PermissionError(Elke27Error):
    """Permission error stub."""


class Elke27PinRequiredError(Elke27Error):
    """PIN required stub."""


class InvalidCredentials(Elke27AuthError):
    """Invalid credentials stub."""


class InvalidPin(Elke27AuthError):
    """Invalid PIN stub."""


class InvalidPinError(Elke27AuthError):
    """Invalid PIN error stub."""


class MissingPinError(Elke27AuthError):
    """Missing PIN error stub."""


_elke27_lib_errors.Elke27Error = Elke27Error
_elke27_lib_errors.Elke27AuthError = Elke27AuthError
_elke27_lib_errors.Elke27LinkRequiredError = Elke27LinkRequiredError
_elke27_lib_errors.Elke27TimeoutError = Elke27TimeoutError
_elke27_lib_errors.Elke27ConnectionError = Elke27ConnectionError
_elke27_lib_errors.Elke27DisconnectedError = Elke27DisconnectedError
_elke27_lib_errors.AuthorizationRequired = AuthorizationRequired
_elke27_lib_errors.Elke27PermissionError = Elke27PermissionError
_elke27_lib_errors.Elke27PinRequiredError = Elke27PinRequiredError
_elke27_lib_errors.InvalidCredentials = InvalidCredentials
_elke27_lib_errors.InvalidPin = InvalidPin
_elke27_lib_errors.InvalidPinError = InvalidPinError
_elke27_lib_errors.MissingPinError = MissingPinError


@dataclass(frozen=True, slots=True)
class FakeClientConfig:
    """Minimal config stub."""


@dataclass(frozen=True, slots=True)
class FakeLinkKeys:
    """Minimal link keys stub."""

    tempkey_hex: str
    linkkey_hex: str
    linkhmac_hex: str

    def to_json(self) -> str:
        """Return a JSON string for storage."""
        return json.dumps(
            {
                "tempkey_hex": self.tempkey_hex,
                "linkkey_hex": self.linkkey_hex,
                "linkhmac_hex": self.linkhmac_hex,
            }
        )


@dataclass(frozen=True, slots=True)
class FakeDiscoveredPanel:
    """Discovered panel stub."""

    host: str
    port: int
    name: str
    model: str
    mac: str


_elke27_lib.ClientConfig = FakeClientConfig
_elke27_lib.DiscoveredPanel = FakeDiscoveredPanel
_elke27_lib.Elke27Client = object
_elke27_lib.LinkKeys = FakeLinkKeys

sys.modules["elke27_lib"] = _elke27_lib
sys.modules["elke27_lib.errors"] = _elke27_lib_errors
sys.modules["elke27_lib.client"] = _elke27_lib_client


class FakeE27Identity:
    """Minimal identity stub."""


class FakeE27LinkKeys:
    """Minimal link keys stub."""


class FakeResult:
    """Minimal result stub."""

    ok = True
    error = None


_elke27_lib_client.E27Identity = FakeE27Identity
_elke27_lib_client.E27LinkKeys = FakeE27LinkKeys
_elke27_lib_client.Elke27Client = object
_elke27_lib_client.Result = FakeResult

from homeassistant import config_entries
from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
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
        assert (args and args[0] is not None) or kwargs.get("config") is not None
        return next(iterator)

    return _factory


@dataclass(frozen=True, slots=True)
class FakePanelInfo:
    """Panel info snapshot stub."""

    panel_name: str
    mac: str
    panel_serial: str


@dataclass(frozen=True, slots=True)
class FakeTableInfo:
    """Table info snapshot stub."""

    areas: int
    zones: int


@dataclass(frozen=True, slots=True)
class FakeSnapshot:
    """Snapshot stub."""

    panel_info: FakePanelInfo
    table_info: FakeTableInfo


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


async def test_manual_link_creates_entry(hass: HomeAssistant) -> None:
    """Test manual host entry creates an entry."""
    discover_client = AsyncMock()
    discover_client.async_discover = AsyncMock(return_value=[])

    link_client = AsyncMock()
    link_client.async_link = AsyncMock(
        return_value=FakeLinkKeys("tk", "lk", "lh")
    )
    link_client.async_connect = AsyncMock(return_value=None)
    link_client.wait_ready = AsyncMock(return_value=True)
    link_client.async_disconnect = AsyncMock(return_value=None)
    link_client.snapshot = FakeSnapshot(
        panel_info=FakePanelInfo(
            panel_name="Test Panel",
            mac="aa:bb:cc:dd:ee:ff",
            panel_serial="1234",
        ),
        table_info=FakeTableInfo(areas=8, zones=16),
    )

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
        assert result["step_id"] == "manual"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.10", CONF_PORT: DEFAULT_PORT},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "link"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"access_code": "1234", "passphrase": "test-pass"},
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Test Panel"
        assert result3["data"][CONF_HOST] == "192.168.1.10"
        assert result3["data"][CONF_PORT] == DEFAULT_PORT
        assert result3["data"][CONF_LINK_KEYS_JSON] == FakeLinkKeys(
            "tk", "lk", "lh"
        ).to_json()
        assert "access_code" not in result3["data"]
        assert "passphrase" not in result3["data"]
        assert result3["data"][CONF_INTEGRATION_SERIAL] == "112233445566"
        assert "panel_info" in result3["options"]
        assert "table_info" in result3["options"]
        link_client.async_disconnect.assert_awaited_once()


async def test_discovery_selection_creates_entry(hass: HomeAssistant) -> None:
    """Test discovery selection path creates an entry."""
    panel = FakeDiscoveredPanel(
        host="192.168.1.20",
        port=DEFAULT_PORT,
        name="Panel A",
        model="E27",
        mac="aa:bb:cc:dd:ee:11",
    )
    discover_client = AsyncMock()
    discover_client.async_discover = AsyncMock(return_value=[panel])

    link_client = AsyncMock()
    link_client.async_link = AsyncMock(
        return_value=FakeLinkKeys("tk", "lk", "lh")
    )
    link_client.async_connect = AsyncMock(return_value=None)
    link_client.wait_ready = AsyncMock(return_value=True)
    link_client.async_disconnect = AsyncMock(return_value=None)
    link_client.snapshot = FakeSnapshot(
        panel_info=FakePanelInfo(
            panel_name="Panel A",
            mac="aa:bb:cc:dd:ee:11",
            panel_serial="5678",
        ),
        table_info=FakeTableInfo(areas=2, zones=4),
    )

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
            {"device": panel.mac},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "link"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"access_code": "1234", "passphrase": "test-pass"},
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["data"][CONF_HOST] == "192.168.1.20"
        assert result3["data"][CONF_PORT] == DEFAULT_PORT
        assert result3["data"][CONF_LINK_KEYS_JSON] == FakeLinkKeys(
            "tk", "lk", "lh"
        ).to_json()
        assert "access_code" not in result3["data"]
        assert "passphrase" not in result3["data"]
        assert result3["data"][CONF_INTEGRATION_SERIAL] == "112233445566"
        link_client.async_disconnect.assert_awaited_once()


async def test_invalid_auth_returns_error(hass: HomeAssistant) -> None:
    """Test invalid auth returns a form error."""
    discover_client = AsyncMock()
    discover_client.async_discover = AsyncMock(return_value=[])

    link_client = AsyncMock()
    link_client.async_link = AsyncMock(side_effect=Elke27AuthError())
    link_client.async_disconnect = AsyncMock(return_value=None)

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
        assert result["step_id"] == "manual"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.30", CONF_PORT: DEFAULT_PORT},
        )
        assert result2["step_id"] == "link"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"access_code": "1234", "passphrase": "bad-pass"},
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"]["base"] == "invalid_auth"
        link_client.async_disconnect.assert_awaited_once()


async def test_cannot_connect_returns_error(hass: HomeAssistant) -> None:
    """Test connection errors return a form error."""
    discover_client = AsyncMock()
    discover_client.async_discover = AsyncMock(return_value=[])

    link_client = AsyncMock()
    link_client.async_link = AsyncMock(
        return_value=FakeLinkKeys("tk", "lk", "lh")
    )
    link_client.async_connect = AsyncMock(side_effect=Elke27TimeoutError())
    link_client.async_disconnect = AsyncMock(return_value=None)

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
        assert result["step_id"] == "manual"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.31", CONF_PORT: DEFAULT_PORT},
        )
        assert result2["step_id"] == "link"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"access_code": "1234", "passphrase": "bad-pass"},
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"]["base"] == "cannot_connect"
        link_client.async_disconnect.assert_awaited_once()


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

    link_client_error = AsyncMock()
    link_client_error.async_link = AsyncMock(
        return_value=FakeLinkKeys("newt", "new", "newh")
    )
    link_client_error.async_connect = AsyncMock(side_effect=Elke27LinkRequiredError())
    link_client_error.async_disconnect = AsyncMock(return_value=None)

    link_client_ok = AsyncMock()
    link_client_ok.async_link = AsyncMock(
        return_value=FakeLinkKeys("newt", "new", "newh")
    )
    link_client_ok.async_connect = AsyncMock(return_value=None)
    link_client_ok.wait_ready = AsyncMock(return_value=True)
    link_client_ok.async_disconnect = AsyncMock(return_value=None)
    link_client_ok.snapshot = FakeSnapshot(
        panel_info=FakePanelInfo(
            panel_name="Panel",
            mac="aa:bb:cc:dd:ee:44",
            panel_serial="9999",
        ),
        table_info=FakeTableInfo(areas=1, zones=1),
    )

    with patch(
        "homeassistant.components.elke27.config_flow.Elke27Client",
        side_effect=_client_factory([link_client_error, link_client_ok]),
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

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "link_required"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"access_code": "1234", "passphrase": "new-pass"},
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reauth_successful"
        assert (
            entry.data[CONF_LINK_KEYS_JSON]
            == FakeLinkKeys("newt", "new", "newh").to_json()
        )
        assert "access_code" not in entry.data
        assert "passphrase" not in entry.data
        link_client_error.async_disconnect.assert_awaited_once()
        link_client_ok.async_disconnect.assert_awaited_once()


async def test_relink_missing_link_keys_updates_entry(hass: HomeAssistant) -> None:
    """Test relink flow updates entry when link keys are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Panel",
        data={
            CONF_HOST: "192.168.1.41",
            CONF_PORT: DEFAULT_PORT,
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    link_client = AsyncMock()
    link_client.async_link = AsyncMock(
        return_value=FakeLinkKeys("newt", "new", "newh")
    )
    link_client.async_connect = AsyncMock(return_value=None)
    link_client.wait_ready = AsyncMock(return_value=True)
    link_client.async_disconnect = AsyncMock(return_value=None)
    link_client.snapshot = FakeSnapshot(
        panel_info=FakePanelInfo(
            panel_name="Panel",
            mac="aa:bb:cc:dd:ee:55",
            panel_serial="8888",
        ),
        table_info=FakeTableInfo(areas=1, zones=1),
    )

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
        assert (
            entry.data[CONF_LINK_KEYS_JSON]
            == FakeLinkKeys("newt", "new", "newh").to_json()
        )
        assert "access_code" not in entry.data
        assert "passphrase" not in entry.data
        link_client.async_disconnect.assert_awaited_once()
