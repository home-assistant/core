"""Test the Elke27 config flow."""

import asyncio
import builtins
from collections.abc import Callable
from dataclasses import dataclass
import importlib
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from elke27_lib import LinkKeys
from elke27_lib.errors import (
    Elke27AuthError,
    Elke27Error,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
    InvalidCredentials,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.elke27 import config_flow
from homeassistant.components.elke27.const import (
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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

    panel: FakePanelInfo
    table_info: FakeTableInfo


def _client_factory(instances: list[AsyncMock]) -> Callable[[], AsyncMock]:
    iterator = iter(instances)

    def _factory() -> AsyncMock:
        return next(iterator)

    return _factory


def test_snapshot_to_dict() -> None:
    """Verify snapshot serialization to dict."""
    data = config_flow._snapshot_to_dict(
        FakePanelInfo(panel_name="Panel", mac="aa:bb", panel_serial="1")
    )
    assert data["panel_name"] == "Panel"
    assert config_flow._snapshot_to_dict({"a": 1}) == {"a": 1}
    assert config_flow._snapshot_to_dict(MappingProxyType({"a": 1})) == {"a": 1}


def test_panel_helpers() -> None:
    """Verify panel info helpers."""
    assert config_flow._panel_name({"panel_name": "Panel 3"}) == "Panel 3"
    assert config_flow._panel_name({"serial": "1234"}) == "1234"
    assert config_flow._panel_unique_id({"serial": "ABC-123"}) == "abc123"
    assert config_flow._panel_unique_id({"mac": "AA:BB:CC:DD:EE:FF"}) == (
        "aabbccddeeff"
    )
    with pytest.raises(ValueError, match="stable identifier"):
        config_flow._panel_unique_id({})


def test_create_client() -> None:
    """Verify client factory returns a client instance."""
    client = config_flow._create_client()
    assert client is not None


async def test_link_and_create_entry_wait_ready_false(hass: HomeAssistant) -> None:
    """Test wait_ready false returns cannot_connect."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.wait_ready = AsyncMock(return_value=False)
    client.async_disconnect = AsyncMock(return_value=None)

    flow = config_flow.Elke27ConfigFlow()
    flow.hass = hass
    flow._context = {}
    flow.flow_id = "flow123"

    with patch(
        "homeassistant.components.elke27.config_flow._create_client",
        side_effect=_client_factory([client]),
    ):
        result = await flow._async_link_and_create_entry(
            host="1.2.3.4",
            port=DEFAULT_PORT,
            access_code="1",
            passphrase="2",
            errors={},
        )
        assert result["errors"]["base"] == "cannot_connect"


async def test_link_and_create_entry_suppresses_disconnect_error(
    hass: HomeAssistant,
) -> None:
    """Test disconnect cleanup errors do not mask flow errors."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.wait_ready = AsyncMock(return_value=False)
    client.async_disconnect = AsyncMock(side_effect=RuntimeError("boom"))

    flow = config_flow.Elke27ConfigFlow()
    flow.hass = hass
    flow._context = {}
    flow.flow_id = "flow123"

    with patch(
        "homeassistant.components.elke27.config_flow._create_client",
        side_effect=_client_factory([client]),
    ):
        result = await flow._async_link_and_create_entry(
            host="1.2.3.4",
            port=DEFAULT_PORT,
            access_code="1",
            passphrase="2",
            errors={},
        )

    assert result["errors"]["base"] == "cannot_connect"
    client.async_disconnect.assert_awaited_once()


async def test_link_and_create_entry_preserves_disconnect_cancellation(
    hass: HomeAssistant,
) -> None:
    """Test disconnect cleanup preserves cancellation."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.wait_ready = AsyncMock(return_value=False)
    client.async_disconnect = AsyncMock(side_effect=asyncio.CancelledError)

    flow = config_flow.Elke27ConfigFlow()
    flow.hass = hass
    flow._context = {}
    flow.flow_id = "flow123"

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await flow._async_link_and_create_entry(
            host="1.2.3.4",
            port=DEFAULT_PORT,
            access_code="1",
            passphrase="2",
            errors={},
        )

    client.async_disconnect.assert_awaited_once()


def test_imports_without_elkm1_lib(monkeypatch: pytest.MonkeyPatch) -> None:
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
    """Test user flow creates an entry."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.async_execute = AsyncMock(return_value=SimpleNamespace(ok=True))
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    client.snapshot = FakeSnapshot(
        panel=FakePanelInfo(
            panel_name="Test Panel",
            mac="aa:bb:cc:dd:ee:ff",
            panel_serial="1234",
        ),
        table_info=FakeTableInfo(areas=8, zones=16),
    )

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

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
        assert result2["result"].unique_id == "1234"
        assert result2["data"][CONF_HOST] == "192.168.1.10"
        assert (
            result2["data"][CONF_LINK_KEYS_JSON] == LinkKeys("tk", "lk", "lh").to_json()
        )
        assert result2["data"][CONF_CLIENT_ID] == config_flow.derive_client_id(
            result["flow_id"]
        )
        assert "panel_info" in result2["options"]
        assert "table_info" in result2["options"]
        client.async_disconnect.assert_awaited_once()


async def test_invalid_auth_returns_error(hass: HomeAssistant) -> None:
    """Test invalid auth returns a form error."""
    client = AsyncMock()
    client.async_link = AsyncMock(side_effect=InvalidCredentials())
    client.async_disconnect = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.30",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "invalid_auth"
        client.async_disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(Elke27TimeoutError(), id="library-timeout"),
        pytest.param(OSError("connection refused"), id="os-error"),
    ],
)
async def test_cannot_connect_returns_error(
    hass: HomeAssistant, error: Exception
) -> None:
    """Test connection errors return a form error."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(side_effect=error)
    client.async_disconnect = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.31",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"
        client.async_disconnect.assert_awaited_once()


async def test_manual_flow_aborts_on_duplicate(hass: HomeAssistant) -> None:
    """Test manual flow aborts if the host/port is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.70", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.70",
            "access_code": "1234",
            "passphrase": "test-pass",
        },
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_manual_flow_updates_duplicate_panel_entry(
    hass: HomeAssistant,
) -> None:
    """Test duplicate panel unique IDs keep the fresh link data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            CONF_HOST: "192.168.1.70",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("old", "old", "old").to_json(),
            CONF_CLIENT_ID: "oldclientid",
        },
    )
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    client.snapshot = FakeSnapshot(
        panel=FakePanelInfo(
            panel_name="Test Panel",
            mac="aa:bb:cc:dd:ee:ff",
            panel_serial="1234",
        ),
        table_info=FakeTableInfo(areas=8, zones=16),
    )

    with patch(
        "homeassistant.components.elke27.config_flow._create_client",
        side_effect=_client_factory([client]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.71",
                "access_code": "1234",
                "passphrase": "test-pass",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.71"
    assert entry.data[CONF_LINK_KEYS_JSON] == LinkKeys("tk", "lk", "lh").to_json()
    assert entry.data[CONF_CLIENT_ID] == config_flow.derive_client_id(result["flow_id"])


async def test_unknown_error_maps_to_unknown(hass: HomeAssistant) -> None:
    """Test unknown client errors map to the unknown config flow error."""
    client = AsyncMock()
    client.async_link = AsyncMock(
        side_effect=Elke27Error("boom", code="boom", is_transient=False)
    )
    client.async_disconnect = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.elke27.config_flow._create_client",
        side_effect=_client_factory([client]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.32",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "unknown"
        client.async_disconnect.assert_awaited_once()


async def test_missing_panel_identifier_maps_to_unknown(hass: HomeAssistant) -> None:
    """Test missing panel identifiers map to a form error."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    client.snapshot = FakeSnapshot(
        panel=FakePanelInfo(panel_name="Test Panel", mac="", panel_serial=""),
        table_info=FakeTableInfo(areas=8, zones=16),
    )

    with patch(
        "homeassistant.components.elke27.config_flow._create_client",
        side_effect=_client_factory([client]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.35",
                "access_code": "1234",
                "passphrase": "test-pass",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "unknown"
    client.async_disconnect.assert_awaited_once()


async def test_auth_error_maps_to_cannot_connect(hass: HomeAssistant) -> None:
    """Test auth error maps to cannot_connect."""
    client = AsyncMock()
    client.async_link = AsyncMock(side_effect=Elke27AuthError())
    client.async_disconnect = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.elke27.config_flow._create_client",
        side_effect=_client_factory([client]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.33",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )
        assert result2["errors"]["base"] == "cannot_connect"


async def test_link_required_maps_to_link_required(hass: HomeAssistant) -> None:
    """Test link-required errors map to link_required."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(side_effect=Elke27LinkRequiredError())
    client.async_disconnect = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.elke27.config_flow._create_client",
        side_effect=_client_factory([client]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.34",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )
        assert result2["errors"]["base"] == "link_required"
