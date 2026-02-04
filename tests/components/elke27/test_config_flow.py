"""Test the Elke27 config flow."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
import importlib
from types import SimpleNamespace
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
from homeassistant.components.elke27.config_flow import STEP_MANUAL_DATA_SCHEMA
from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import HomeAssistantError

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

    panel_info: FakePanelInfo
    table_info: FakeTableInfo


@dataclass(frozen=True, slots=True)
class FakePanel:
    """Discovered panel stub."""

    panel_host: str
    panel_port: int
    panel_name: str
    panel_mac: str
    panel_model: str


def _client_factory(instances: list[AsyncMock]) -> callable:
    iterator = iter(instances)

    def _factory() -> AsyncMock:
        return next(iterator)

    return _factory


def test_panel_helpers() -> None:
    """Verify panel helper conversions."""
    panel = FakePanel(
        panel_host="1.2.3.4",
        panel_port=2101,
        panel_name="Panel",
        panel_mac="aa:bb",
        panel_model="E27",
    )
    panel_dict = config_flow._panel_to_dict(panel)
    assert panel_dict["host"] == "1.2.3.4"
    assert panel_dict["port"] == 2101
    assert panel_dict["name"] == "Panel"
    assert panel_dict["mac"] == "aa:bb"
    assert panel_dict["model"] == "E27"

    normalized = config_flow._normalize_panel_keys(
        {
            "ip": "1.2.3.5",
            "panel_port": 2102,
            "panel_name": "Panel 2",
            "panel_mac": "cc:dd",
            "panel_model": "E27",
        }
    )
    assert normalized["host"] == "1.2.3.5"
    assert normalized["port"] == 2102
    assert normalized["name"] == "Panel 2"
    assert normalized["mac"] == "cc:dd"
    assert config_flow._panel_mac({"mac": "ee:ff"}) == "ee:ff"
    assert config_flow._panel_name({"panel_name": "Panel 3"}) == "Panel 3"
    assert config_flow._panel_label(panel) == "Panel (1.2.3.4)"
    assert config_flow._panel_to_dict(None) == {}
    assert config_flow._panel_label(SimpleNamespace(host="1.2.3.5")) == "1.2.3.5"
    assert config_flow._panel_label(SimpleNamespace(name="Only Name")) == "Only Name"
    assert config_flow._panel_label(SimpleNamespace()) == "Panel"
    assert config_flow._panel_to_dict({"host": "1.2.3.4"})["host"] == "1.2.3.4"
    assert config_flow._panel_to_dict(FakePanel(
        panel_host="1.2.3.4",
        panel_port=2101,
        panel_name="Panel",
        panel_mac="aa:bb",
        panel_model="E27",
    ))["host"] == "1.2.3.4"


def test_snapshot_to_dict() -> None:
    """Verify snapshot serialization to dict."""
    snapshot = FakeSnapshot(
        panel_info=FakePanelInfo(panel_name="Panel", mac="aa:bb", panel_serial="1"),
        table_info=FakeTableInfo(areas=1, zones=2),
    )
    data = config_flow._snapshot_to_dict(snapshot)
    assert data["panel_info"]["panel_name"] == "Panel"
    assert data["table_info"]["areas"] == 1
    assert config_flow._snapshot_to_dict({"a": 1}) == {"a": 1}
    assert config_flow._snapshot_to_dict(None) == {}

    class Obj:
        def __init__(self) -> None:
            self.value = 1
            self._hidden = 2

    assert config_flow._snapshot_to_dict(Obj()) == {"value": 1}


def test_create_client() -> None:
    """Verify client factory returns a client instance."""
    client = config_flow._create_client()
    assert client is not None


async def test_discover_invalid_panel_index(hass: HomeAssistant) -> None:
    """Test discover step handles invalid panel index."""
    discovery = SimpleNamespace(panel_host="1.2.3.4", port=DEFAULT_PORT)
    with patch(
        "homeassistant.components.elke27.config_flow.AIOELKDiscovery.async_scan",
        AsyncMock(return_value=[discovery]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "discover"},
        )
        with pytest.raises(InvalidData):
            await hass.config_entries.flow.async_configure(
                result2["flow_id"],
                {"panel": "99", "access_code": "1", "passphrase": "2"},
            )


async def test_discover_missing_host(hass: HomeAssistant) -> None:
    """Test discover step handles missing host."""
    discovery = SimpleNamespace(panel_host=None, port=DEFAULT_PORT)
    with patch(
        "homeassistant.components.elke27.config_flow.AIOELKDiscovery.async_scan",
        AsyncMock(return_value=[discovery]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "discover"},
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"panel": "0", "access_code": "1", "passphrase": "2"},
        )
        assert result3["errors"]["base"] == "no_panels_found"


async def test_discover_handles_missing_panels(hass: HomeAssistant) -> None:
    """Test discover handles missing panel list."""
    flow = config_flow.Elke27ConfigFlow()
    flow.hass = hass
    flow._discovered_panels = None
    result = await flow.async_step_discover({"panel": "0", "access_code": "1", "passphrase": "2"})
    assert result["errors"]["base"] == "no_panels_found"


async def test_link_and_create_entry_missing_host(hass: HomeAssistant) -> None:
    """Test link/create returns unknown when host/port missing."""
    flow = config_flow.Elke27ConfigFlow()
    flow.hass = hass
    result = await flow._async_link_and_create_entry(
        access_code="1",
        passphrase="2",
        errors={},
        step_id="manual",
        data_schema=STEP_MANUAL_DATA_SCHEMA,
    )
    assert result["errors"]["base"] == "unknown"


async def test_relink_missing_context(hass: HomeAssistant) -> None:
    """Verify relink aborts when missing context."""
    flow = config_flow.Elke27ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_relink({"access_code": "1", "passphrase": "2"})
    assert result["reason"] == "missing_context"


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
    flow._selected_host = "1.2.3.4"
    flow._selected_port = DEFAULT_PORT

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233"),
        ),
    ):
        result = await flow._async_link_and_create_entry(
            access_code="1",
            passphrase="2",
            errors={},
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
        )
        assert result["errors"]["base"] == "cannot_connect"


async def test_create_entry_adds_title_when_missing(hass: HomeAssistant) -> None:
    """Verify created entry gets a title if missing."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    client.snapshot = FakeSnapshot(
        panel_info=FakePanelInfo(panel_name="Panel", mac="aa", panel_serial="1"),
        table_info=FakeTableInfo(areas=1, zones=1),
    )

    flow = config_flow.Elke27ConfigFlow()
    flow.hass = hass
    flow._selected_host = "1.2.3.4"
    flow._selected_port = DEFAULT_PORT

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233"),
        ),
        patch.object(
            flow,
            "async_create_entry",
            return_value={"type": "create_entry", "data": {}},
        ),
        patch.object(
            flow,
            "async_set_unique_id",
            AsyncMock(return_value=None),
        ),
    ):
        result = await flow._async_link_and_create_entry(
            access_code="1",
            passphrase="2",
            errors={},
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
        )
        assert result["title"] == "Panel"


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
        panel_info=FakePanelInfo(
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
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
        patch("homeassistant.components.elke27.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "manual"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "manual"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.10",
                "access_code": "1234",
                "passphrase": "test-pass",
            },
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Test Panel"
        assert result3["data"][CONF_HOST] == "192.168.1.10"
        assert (
            result3["data"][CONF_LINK_KEYS_JSON] == LinkKeys("tk", "lk", "lh").to_json()
        )
        assert result3["data"][CONF_INTEGRATION_SERIAL] == "112233445566"
        assert "panel_info" in result3["options"]
        assert "table_info" in result3["options"]
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
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "manual"},
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.30",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"]["base"] == "invalid_auth"
        client.async_disconnect.assert_awaited_once()


async def test_cannot_connect_returns_error(hass: HomeAssistant) -> None:
    """Test connection errors return a form error."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(side_effect=Elke27TimeoutError())
    client.async_disconnect = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "manual"},
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.31",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )

        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"]["base"] == "cannot_connect"
        client.async_disconnect.assert_awaited_once()


async def test_discovery_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test discovery flow creates an entry."""
    client = AsyncMock()
    client.async_link = AsyncMock(return_value=LinkKeys("tk", "lk", "lh"))
    client.async_connect = AsyncMock(return_value=None)
    client.async_execute = AsyncMock(return_value=SimpleNamespace(ok=True))
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    client.snapshot = FakeSnapshot(
        panel_info=FakePanelInfo(
            panel_name="Test Panel",
            mac="aa:bb:cc:dd:ee:ff",
            panel_serial="1234",
        ),
        table_info=FakeTableInfo(areas=8, zones=16),
    )

    discovery = SimpleNamespace(
        panel_host="192.168.1.20",
        port=DEFAULT_PORT,
        panel_name="Discovered Panel",
        panel_mac="aa:bb:cc:dd:ee:00",
    )

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.AIOELKDiscovery.async_scan",
            AsyncMock(return_value=[discovery]),
        ),
        patch("homeassistant.components.elke27.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "discover"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "discover"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "panel": "0",
                "access_code": "1234",
                "passphrase": "test-pass",
            },
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Test Panel"
        assert result3["data"][CONF_HOST] == "192.168.1.20"
        assert (
            result3["data"][CONF_LINK_KEYS_JSON] == LinkKeys("tk", "lk", "lh").to_json()
        )
        assert result3["data"][CONF_INTEGRATION_SERIAL] == "112233445566"
        assert "panel_info" in result3["options"]
        assert "table_info" in result3["options"]
        client.async_disconnect.assert_awaited_once()


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
        return_value=LinkKeys("newt", "new", "newh")
    )
    link_client_error.async_connect = AsyncMock(side_effect=Elke27LinkRequiredError())
    link_client_error.async_disconnect = AsyncMock(return_value=None)

    link_client_ok = AsyncMock()
    link_client_ok.async_link = AsyncMock(return_value=LinkKeys("newt", "new", "newh"))
    link_client_ok.async_connect = AsyncMock(return_value=None)
    link_client_ok.async_execute = AsyncMock(return_value=SimpleNamespace(ok=True))
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

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([link_client_error, link_client_ok]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
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
            entry.data[CONF_LINK_KEYS_JSON] == LinkKeys("newt", "new", "newh").to_json()
        )
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
    link_client.async_link = AsyncMock(return_value=LinkKeys("newt", "new", "newh"))
    link_client.async_connect = AsyncMock(return_value=None)
    link_client.async_execute = AsyncMock(return_value=SimpleNamespace(ok=True))
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

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([link_client]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
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
            entry.data[CONF_LINK_KEYS_JSON] == LinkKeys("newt", "new", "newh").to_json()
        )
        link_client.async_disconnect.assert_awaited_once()


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
    assert result["type"] is FlowResultType.MENU

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "manual"},
    )
    assert result2["type"] is FlowResultType.FORM

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_HOST: "192.168.1.70",
            "access_code": "1234",
            "passphrase": "test-pass",
        },
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


async def test_reauth_missing_context_aborts(hass: HomeAssistant) -> None:
    """Test reauth flow aborts when entry context is missing."""
    with pytest.raises(HomeAssistantError):
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
        )


async def test_discovery_no_panels_found(hass: HomeAssistant) -> None:
    """Test discovery step reports no panels found."""
    with patch(
        "homeassistant.components.elke27.config_flow.AIOELKDiscovery.async_scan",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "discover"},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "no_panels_found"


async def test_unknown_error_maps_to_unknown(hass: HomeAssistant) -> None:
    """Test unknown client errors map to the unknown config flow error."""
    client = AsyncMock()
    client.async_link = AsyncMock(
        side_effect=Elke27Error("boom", code="boom", is_transient=False)
    )
    client.async_disconnect = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "manual"},
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.32",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"]["base"] == "unknown"
        client.async_disconnect.assert_awaited_once()


async def test_auth_error_maps_to_cannot_connect(hass: HomeAssistant) -> None:
    """Test auth error maps to cannot_connect."""
    client = AsyncMock()
    client.async_link = AsyncMock(side_effect=Elke27AuthError())
    client.async_disconnect = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.elke27.config_flow._create_client",
            side_effect=_client_factory([client]),
        ),
        patch(
            "homeassistant.components.elke27.config_flow.async_get_integration_serial",
            AsyncMock(return_value="112233445566"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "manual"},
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_HOST: "192.168.1.33",
                "access_code": "1234",
                "passphrase": "bad-pass",
            },
        )
        assert result3["errors"]["base"] == "cannot_connect"
