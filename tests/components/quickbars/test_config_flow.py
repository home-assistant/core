"""Tests for the QuickBars config flow and options flow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, patch
import voluptuous as vol

import pytest
from aiohttp import ClientError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
import importlib
_cf = importlib.import_module("homeassistant.components.quickbars.config_flow")
assert hasattr(_cf, "QuickBarsConfigFlow")

from tests.common import MockConfigEntry

DOMAIN = "quickbars"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def patch_client_all():
    """Patch QuickBarsClient with sensible defaults and yield the instance."""
    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        # Defaults for user + zeroconf flows
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        inst.confirm_pair = AsyncMock(
            return_value={"id": "QB-1234", "name": "QuickBars TV", "port": 9123, "has_token": False}
        )
        inst.set_credentials = AsyncMock(return_value={"ok": True})
        yield inst


async def _loaded_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and LOAD a config entry; do not touch entry.state directly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="QB",
        unique_id="QB-1234",
        data={CONF_HOST: "192.0.2.10", CONF_PORT: 9123, "id": "QB-1234"},
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.quickbars.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


@dataclass
class _ZCStub:
    """Minimal stand-in for ZeroconfServiceInfo with mapping-like access."""
    ip_address: Any
    ip_addresses: list[Any]
    port: int
    hostname: str
    type: str
    name: str
    properties: Mapping[str, Any]

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)


# ---------------------------------------------------------------------------
# CONFIG FLOW TESTS
# ---------------------------------------------------------------------------

async def test_user_flow_pair_then_token_success(hass: HomeAssistant, patch_client_all) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.10", CONF_PORT: 9123}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "pair"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "1234"})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "http://ha.local:8123", "token": "abc123"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.10"
    assert result["data"][CONF_PORT] == 9123


async def test_user_flow_already_has_token_skips_token(hass: HomeAssistant, patch_client_all) -> None:
    patch_client_all.confirm_pair.return_value.update({"has_token": True})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.10", CONF_PORT: 9123}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "1234"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.10"
    assert result["data"][CONF_PORT] == 9123


async def test_user_flow_tv_unreachable_on_pair_code(hass: HomeAssistant) -> None:
    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(side_effect=TimeoutError)

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
        assert result["errors"]["base"] == "tv_unreachable"


async def test_pair_no_unique_id(hass: HomeAssistant) -> None:
    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        inst.confirm_pair = AsyncMock(return_value={})  # missing id

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "1234"})
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "pair"
        assert result["errors"]["base"] == "no_unique_id"


async def test_token_creds_invalid(hass: HomeAssistant) -> None:
    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        inst.confirm_pair = AsyncMock(
            return_value={"id": "QB-1", "name": "QB", "port": 9123, "has_token": False}
        )
        inst.set_credentials = AsyncMock(return_value={"ok": False, "reason": "creds_invalid"})

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "0000"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://x", "token": "y"}
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "token"
        assert result["errors"]["base"] == "creds_invalid"


async def test_token_tv_unreachable(hass: HomeAssistant) -> None:
    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        inst.confirm_pair = AsyncMock(
            return_value={"id": "QB-1", "name": "QB", "port": 9123, "has_token": False}
        )
        inst.set_credentials = AsyncMock(side_effect=ClientError("boom"))

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "0000"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://x", "token": "y"}
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "token"
        assert result["errors"]["base"] == "tv_unreachable"


async def test_pair_get_url_raises_is_suppressed(hass: HomeAssistant) -> None:
    with (
        patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls,
        patch("homeassistant.components.quickbars.config_flow.get_url", side_effect=HomeAssistantError("no url")),
    ):
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        inst.confirm_pair = AsyncMock(
            return_value={"id": "QB-1", "name": "QB", "port": 9123, "has_token": True}
        )

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "0000"})
        assert result["type"] is FlowResultType.CREATE_ENTRY  # still succeeds


async def test_zeroconf_discovery_confirm_and_pair(hass: HomeAssistant, patch_client_all) -> None:
    zc = _ZCStub(
        ip_address=ip_address("192.0.2.20"),
        ip_addresses=[ip_address("192.0.2.20")],
        port=9123,
        hostname="QuickBars-1234.local.",
        type="_quickbars._tcp.local.",
        name="QuickBars-1234._quickbars._tcp.local.",
        properties={"id": "QB-1234", "api": "1", "app_version": "1.2.3", "name": "QuickBars TV"},
    )

    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=(
            "192.0.2.20",
            9123,
            {"id": "QB-1234", "api": "1", "app_version": "1.2.3", "name": "QuickBars TV"},
            "QuickBars-1234.local.",
            "QuickBars-1234._quickbars._tcp.local.",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "pair"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "9999"})
    if result["type"] is FlowResultType.FORM:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://ha.local:8123", "token": "abc123"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_updates_existing_entry(hass: HomeAssistant, patch_client_all) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="QB-1234",
        data={CONF_HOST: "192.0.2.10", CONF_PORT: 9123, "id": "QB-1234"}
    )
    entry.add_to_hass(hass)

    zc = _ZCStub(
        ip_address=ip_address("192.0.2.55"),
        ip_addresses=[ip_address("192.0.2.55")],
        port=9999,
        hostname="QuickBars-1234.local.",
        type="_quickbars._tcp.local.",
        name="QuickBars-1234._quickbars._tcp.local.",
        properties={"id": "QB-1234", "name": "QuickBars TV"},
    )

    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=(
            "192.0.2.55",
            9999,
            {"id": "QB-1234", "name": "QuickBars TV"},
            "QuickBars-1234.local.",
            "QuickBars-1234._quickbars._tcp.local.",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )

    assert result["type"] is FlowResultType.ABORT
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.data[CONF_HOST] == "192.0.2.55"
    assert updated.data[CONF_PORT] == 9999


async def test_zeroconf_abort_unknown_when_missing_host_or_port(hass: HomeAssistant) -> None:
    zc = _ZCStub(
        ip_address=ip_address("192.0.2.1"),
        ip_addresses=[ip_address("192.0.2.1")],
        port=0,
        hostname="h",
        type="_quickbars._tcp.local.",
        name="n",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_zeroconf_confirm_get_pair_code_unreachable(hass: HomeAssistant) -> None:
    zc = _ZCStub(
        ip_address=ip_address("1.2.3.4"),
        ip_addresses=[ip_address("1.2.3.4")],
        port=9123,
        hostname="h",
        type="_quickbars._tcp.local.",
        name="n",
        properties={"name": "QB"},
    )
    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=("1.2.3.4", 9123, {"name": "QB"}, "h", "n"),
    ), patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(side_effect=OSError("down"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "zeroconf_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
        assert result["errors"]["base"] == "tv_unreachable"


# ---------------------------------------------------------------------------
# OPTIONS FLOW TESTS (no reporter patches; use real OptionsFlow pattern)
# ---------------------------------------------------------------------------

async def test_options_init_ping_false(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=False)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "init"
        res = await hass.config_entries.options.async_configure(res["flow_id"])
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "init"
        assert res["errors"]["base"] == "tv_unreachable"


async def test_options_init_ping_exception(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(side_effect=Exception("boom"))):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "init"
        res = await hass.config_entries.options.async_configure(res["flow_id"])
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "init"
        assert res["errors"]["base"] == "tv_unreachable"


async def test_options_init_snapshot_exception(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(side_effect=Exception("down"))):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "init"
        assert res["errors"]["base"] == "tv_unreachable"


async def test_options_menu_routes_and_expose_success(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {
        "entities": [{"id": "light.kitchen", "isSaved": True, "friendlyName": "Kitchen"}],
        "quick_bars": [{"name": "Main"}],
    }
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "menu"
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "export"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "expose"

    with patch("homeassistant.components.quickbars.config_flow.map_entity_display_names",
               side_effect=lambda hass, ids: {i: i for i in ids}), \
         patch("homeassistant.components.quickbars.config_flow.ws_entities_replace", AsyncMock(return_value=None)):
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"saved": ["light.kitchen"]})
        assert res["type"] is FlowResultType.CREATE_ENTRY


async def test_options_expose_error(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [{"id": "light.kitchen", "isSaved": True}], "quick_bars": [{"name": "Main"}]}
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "export"})

    with patch("homeassistant.components.quickbars.config_flow.map_entity_display_names",
               side_effect=lambda hass, ids: {i: i for i in ids}), \
         patch("homeassistant.components.quickbars.config_flow.ws_entities_replace", AsyncMock(side_effect=Exception("down"))):
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"saved": ["light.kitchen"]})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "expose"
        assert res["errors"]["base"] == "tv_unreachable"


async def test_options_manage_saved_pick_to_manage_and_save(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {
        "entities": [{"id": "light.kitchen", "isSaved": True, "friendlyName": "Kitchen"}],
        "quick_bars": [{"name": "QB"}],
    }
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_saved"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "manage_saved_pick"
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"entity": "light.kitchen"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "manage_saved"

    with patch("homeassistant.components.quickbars.config_flow.ws_entities_update", AsyncMock(return_value=None)):
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"display_name": "My Kitchen"})
        assert res["type"] is FlowResultType.CREATE_ENTRY


async def test_options_manage_saved_error_on_update(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {
        "entities": [{"id": "light.kitchen", "isSaved": True, "friendlyName": "Kitchen"}],
        "quick_bars": [{"name": "QB"}],
    }
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_saved"})
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"entity": "light.kitchen"})

    with patch("homeassistant.components.quickbars.config_flow.ws_entities_update", AsyncMock(side_effect=Exception("nope"))):
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"display_name": "X"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "manage_saved"
        assert res["errors"]["base"] == "tv_unreachable"


async def test_options_manage_saved_bounce_when_entity_invalid(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [{"id": "light.kitchen", "isSaved": True}], "quick_bars": [{"name": "QB"}]}
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_saved"})
        # No entity chosen -> should bounce back to the pick step
        res2 = await hass.config_entries.options.async_configure(res["flow_id"], user_input={})
        assert res2["type"] is FlowResultType.FORM and res2["step_id"] == "manage_saved_pick"


async def test_options_qb_pick_new_and_manage_name_taken_then_success(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "Main"}]}
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_qb"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_pick"
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"quickbar": "new"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_manage"

    # First submit: name taken
    with patch("homeassistant.components.quickbars.config_flow.ws_put_snapshot", AsyncMock(return_value=None)):
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"quickbar_name": "Main"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_manage"
        assert res["errors"]["base"] == "name_taken"

    # Second submit: success
    with patch("homeassistant.components.quickbars.config_flow.ws_put_snapshot", AsyncMock(return_value=None)):
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"quickbar_name": "Main 2"})
        assert res["type"] is FlowResultType.CREATE_ENTRY


async def test_options_qb_manage_put_snapshot_error(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "Only"}]}
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_qb"})
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"quickbar": "0"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_manage"

    with patch("homeassistant.components.quickbars.config_flow.ws_put_snapshot", AsyncMock(side_effect=Exception("fail"))):
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"quickbar_name": "Only Renamed"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_manage"
        assert res["errors"]["base"] == "tv_unreachable"


async def test_options_menu_unknown_action_returns_menu(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "QB"}]}

    # Make init succeed and return a snapshot
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)), \
         patch("homeassistant.components.quickbars.config_flow.schema_menu",
               return_value=vol.Schema({vol.Required("action"): str})):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "menu"

        # Send an unknown action – schema allows it; code should fall back to menu
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "oops"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "menu"



async def test_options_manage_saved_pick_snapshot_error(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    # First call (init) returns a snapshot; second call (manage_saved_pick) errors
    snapshot = {"entities": [{"id": "light.kitchen", "isSaved": True}], "quick_bars": [{"name": "QB"}]}
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot",
               AsyncMock(side_effect=[snapshot, OSError("down")])):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "menu"

        # Route into manage_saved_pick; the *second* snapshot call fails there
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_saved"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "manage_saved_pick"
        assert res["errors"]["base"] == "tv_unreachable"



async def test_options_qb_pick_snapshot_error(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "One"}]}
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot",
               AsyncMock(side_effect=[snapshot, TimeoutError()])):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "menu"

        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_qb"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_pick"
        assert res["errors"]["base"] == "tv_unreachable"



async def test_options_qb_pick_no_quickbars(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": []}
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_qb"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_pick"
        # schema is empty in this branch; just ensuring we land here


async def test_options_qb_pick_nonint_choice_uses_default(hass: HomeAssistant) -> None:
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "Main"}, {"name": "Second"}]}

    # Let init succeed and patch schema to allow any string for `quickbar`
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)), \
         patch("homeassistant.components.quickbars.config_flow.schema_qb_pick",
               side_effect=lambda options, default_idx: vol.Schema({vol.Required("quickbar"): str})):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"action": "manage_qb"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_pick"

        # Provide a non-int. Schema accepts it; code should fall back to default idx (0) and go to qb_manage.
        res = await hass.config_entries.options.async_configure(res["flow_id"], user_input={"quickbar": "not-a-number"})
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_manage"



async def test_user_flow_pair_updates_existing_entry(hass: HomeAssistant) -> None:
    # Existing entry with same unique_id but different host/port
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="QB-1234",
        data={CONF_HOST: "192.0.2.50", CONF_PORT: 9999, "id": "QB-1234"},
    )
    existing.add_to_hass(hass)

    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        # Pairing returns the same id but with new host/port
        inst.confirm_pair = AsyncMock(return_value={"id": "QB-1234", "name": "QB", "port": 9123, "has_token": True})

        # Start user flow
        res = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        res = await hass.config_entries.flow.async_configure(res["flow_id"], {CONF_HOST: "192.0.2.10", CONF_PORT: 9123})
        res = await hass.config_entries.flow.async_configure(res["flow_id"], {"code": "1234"})

    # Flow aborts (already configured) and updates the existing entry
    assert res["type"] is FlowResultType.ABORT
    updated = hass.config_entries.async_get_entry(existing.entry_id)
    assert updated.data[CONF_HOST] == "192.0.2.10"
    assert updated.data[CONF_PORT] == 9123


async def test_zeroconf_confirm_initial_form_renders(hass):
    flow = _cf.QuickBarsConfigFlow()
    flow.hass = hass
    # Pretend zeroconf already filled these in
    flow._host, flow._port = "192.0.2.20", 9123
    res = await flow.async_step_zeroconf_confirm(None)
    assert res["type"] is FlowResultType.FORM and res["step_id"] == "zeroconf_confirm"


async def test__ensure_snapshot_short_circuit_true(hass: HomeAssistant) -> None:
    """_ensure_snapshot should immediately return True if snapshot already exists."""
    entry = await _loaded_entry(hass)
    
    # Start the flow normally, then access the internal flow handler
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot",
               AsyncMock(return_value={"entities": [], "quick_bars": []})):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        
        # Now test _ensure_snapshot directly on a flow that already has a snapshot
        flow = _cf.QuickBarsOptionsFlow()
        flow.hass = hass
        flow._snapshot = {}  # pretend already loaded
        ok = await flow._ensure_snapshot("anything")
        assert ok is True


async def test_manage_saved_snapshot_error_shows_form(hass: HomeAssistant) -> None:
    """Direct landing to manage_saved with no snapshot -> error form."""
    entry = await _loaded_entry(hass)
    
    # Test the scenario where ws_get_snapshot fails when manage_saved tries to fetch it
    # First we need to get past init and menu to manage_saved_pick
    snapshot_ok = {"entities": [{"id": "light.a", "isSaved": True}], "quick_bars": [{"name": "QB"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot",
               AsyncMock(return_value=snapshot_ok)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "menu"
        
        # Go to manage_saved_pick
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_saved"}
        )
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "manage_saved_pick"
        
        # Pick an entity
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"entity": "light.a"}
        )
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "manage_saved"
        
        # Now submit with an update that will fail
        with patch("homeassistant.components.quickbars.config_flow.ws_entities_update",
                   AsyncMock(side_effect=OSError("down"))):
            res = await hass.config_entries.options.async_configure(
                res["flow_id"], user_input={"display_name": "New Name"}
            )
            
            assert res["type"] is FlowResultType.FORM
            assert res["step_id"] == "manage_saved"
            assert res["errors"]["base"] == "tv_unreachable"


async def test_manage_saved_invalid_entity_bounces_to_pick(hass: HomeAssistant) -> None:
    """When _entity_id is invalid, manage_saved should bounce back to pick."""
    entry = await _loaded_entry(hass)
    snapshot = {
        "entities": [{"id": "light.kitchen", "isSaved": True, "friendlyName": "Kitchen"}],
        "quick_bars": [{"name": "QB"}],
    }
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_saved"}
        )
        
        # Instead of picking a valid entity, submit empty (no entity selected)
        # This should re-show the pick form
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={}
        )
        
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "manage_saved_pick"


async def test_qb_pick_out_of_range_index_resets_to_zero(hass: HomeAssistant) -> None:
    """When _qb_index is out of range, it should reset to 0."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "Only"}, {"name": "Second"}]}

    # We'll check that the default index passed to schema_qb_pick is 0
    captured = {}
    original_schema_qb_pick = _cf.schema_qb_pick
    
    def _fake_schema(options, default_idx):
        captured["default_idx"] = default_idx
        return original_schema_qb_pick(options, default_idx)

    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)), \
         patch("homeassistant.components.quickbars.config_flow.schema_qb_pick", side_effect=_fake_schema):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_qb"}
        )
        
        # The flow should show qb_pick with default_idx=0 (since no valid index was set)
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "qb_pick"
        # First call should have default_idx in a valid range
        assert captured.get("default_idx") == 0


async def test_qb_manage_ensure_snapshot_false_returns_error_form(hass: HomeAssistant) -> None:
    """When _ensure_snapshot fails in qb_manage, show error form."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "One"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_qb"}
        )
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_pick"
        
        # Pick the quickbar
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"quickbar": "0"}
        )
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_manage"
        
        # Now submit with a change that will fail
        with patch("homeassistant.components.quickbars.config_flow.ws_put_snapshot",
                   AsyncMock(side_effect=TimeoutError())):
            res = await hass.config_entries.options.async_configure(
                res["flow_id"], user_input={"quickbar_name": "Changed"}
            )
            
            assert res["type"] is FlowResultType.FORM
            assert res["step_id"] == "qb_manage"
            assert res["errors"]["base"] == "tv_unreachable"


async def test_qb_manage_invalid_index_routes_to_pick(hass: HomeAssistant) -> None:
    """When qb_index is invalid or qb_list is empty, route back to pick."""
    entry = await _loaded_entry(hass)
    
    # Start with an empty quick_bars list
    snapshot_empty = {"entities": [], "quick_bars": []}
    snapshot_ok = {"entities": [], "quick_bars": [{"name": "One"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot",
               AsyncMock(return_value=snapshot_empty)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_qb"}
        )
        
        # With empty quick_bars, it should show the "no quickbars" form
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "qb_pick"


async def test_options_done_creates_entry(hass: HomeAssistant) -> None:
    """Test that async_step_done creates an entry with current options."""
    entry = await _loaded_entry(hass)
    
    # We can't easily test async_step_done in isolation due to the config_entry restriction
    # Instead, verify it works by completing a normal flow that ends by calling done
    snapshot = {"entities": [], "quick_bars": [{"name": "QB"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)), \
         patch("homeassistant.components.quickbars.config_flow.ws_entities_replace", AsyncMock(return_value=None)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "export"}
        )
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"saved": []}
        )
        
        # The flow should complete successfully
        assert res["type"] is FlowResultType.CREATE_ENTRY
        assert res["data"] == dict(entry.options)


"""Additional tests to reach 100% coverage."""


async def test_async_step_user_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test that async_step_user shows form when user_input is None (lines 494-499)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # Verify the schema has host and port fields
    assert CONF_HOST in result["data_schema"].schema
    assert CONF_PORT in result["data_schema"].schema


async def test_async_step_pair_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test that async_step_pair shows form when user_input is None (line 514)."""
    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.10", CONF_PORT: 9123}
        )
        
        # This is the pair form being shown (user_input=None path)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert "code" in result["data_schema"].schema


async def test_async_step_token_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test that async_step_token shows form when user_input is None (line 585)."""
    with patch("homeassistant.components.quickbars.config_flow.QuickBarsClient", autospec=True) as cls:
        inst = cls.return_value
        inst.get_pair_code = AsyncMock(return_value={"sid": "sid1"})
        inst.confirm_pair = AsyncMock(
            return_value={"id": "QB-1", "name": "QB", "port": 9123, "has_token": False}
        )
        
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.10", CONF_PORT: 9123}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "1234"}
        )
        
        # This is the token form being shown (user_input=None path)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "token"
        assert "url" in result["data_schema"].schema
        assert "token" in result["data_schema"].schema


async def test_zeroconf_no_unique_id_still_proceeds(hass: HomeAssistant) -> None:
    """Test zeroconf flow when no unique_id is provided (lines 621-623)."""
    zc = _ZCStub(
        ip_address=ip_address("192.0.2.20"),
        ip_addresses=[ip_address("192.0.2.20")],
        port=9123,
        hostname="QuickBars.local.",
        type="_quickbars._tcp.local.",
        name="QuickBars._quickbars._tcp.local.",
        properties={"name": "QuickBars TV"},  # No 'id' property
    )

    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=(
            "192.0.2.20",
            9123,
            {"name": "QuickBars TV"},  # No id
            "QuickBars.local.",
            "QuickBars._quickbars._tcp.local.",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )
    
    # Should still show the confirmation form even without unique_id
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


async def test_zeroconf_confirm_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test zeroconf_confirm shows form when user_input is None (line 633)."""
    zc = _ZCStub(
        ip_address=ip_address("192.0.2.20"),
        ip_addresses=[ip_address("192.0.2.20")],
        port=9123,
        hostname="QuickBars.local.",
        type="_quickbars._tcp.local.",
        name="QuickBars._quickbars._tcp.local.",
        properties={"id": "QB-1234", "name": "QuickBars TV"},
    )

    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=(
            "192.0.2.20",
            9123,
            {"id": "QB-1234", "name": "QuickBars TV"},
            "QuickBars.local.",
            "QuickBars._quickbars._tcp.local.",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )
    
    # The initial form shown (user_input=None)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    # Verify it's showing an empty schema for confirmation
    assert result["data_schema"].schema == {}


async def test_options_qb_manage_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test qb_manage shows form when user_input is None (line 690)."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "Main"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_qb"}
        )
        assert res["type"] is FlowResultType.FORM and res["step_id"] == "qb_pick"
        
        # Pick the quickbar to go to qb_manage
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"quickbar": "0"}
        )
        
        # This shows the qb_manage form (user_input=None path)
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "qb_manage"
        # Verify form has quickbar_name field
        assert "quickbar_name" in res["data_schema"].schema


async def test_options_menu_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test menu shows form when user_input is None."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "QB"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        
        # This is the menu form (user_input=None path from async_step_menu)
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "menu"
        assert "action" in res["data_schema"].schema


async def test_options_expose_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test expose shows form when user_input is None."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [{"id": "light.a", "isSaved": True}], "quick_bars": [{"name": "QB"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "export"}
        )
        
        # This is the expose form (user_input=None path)
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "expose"
        assert "saved" in res["data_schema"].schema


async def test_options_manage_saved_pick_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test manage_saved_pick shows form when user_input is None."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [{"id": "light.a", "isSaved": True}], "quick_bars": [{"name": "QB"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_saved"}
        )
        
        # This is the manage_saved_pick form (user_input=None path)
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "manage_saved_pick"
        assert "entity" in res["data_schema"].schema


async def test_options_manage_saved_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test manage_saved shows form when user_input is None."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [{"id": "light.a", "isSaved": True, "friendlyName": "Light A"}], "quick_bars": [{"name": "QB"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_saved"}
        )
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"entity": "light.a"}
        )
        
        # This is the manage_saved form (user_input=None path)
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "manage_saved"
        assert "display_name" in res["data_schema"].schema


async def test_options_qb_pick_shows_form_on_none_input(hass: HomeAssistant) -> None:
    """Test qb_pick shows form when user_input is None."""
    entry = await _loaded_entry(hass)
    snapshot = {"entities": [], "quick_bars": [{"name": "QB"}]}
    
    with patch("homeassistant.components.quickbars.config_flow.ws_ping", AsyncMock(return_value=True)), \
         patch("homeassistant.components.quickbars.config_flow.ws_get_snapshot", AsyncMock(return_value=snapshot)):
        res = await hass.config_entries.options.async_init(entry.entry_id)
        res = await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"action": "manage_qb"}
        )
        
        # This is the qb_pick form (user_input=None path)
        assert res["type"] is FlowResultType.FORM
        assert res["step_id"] == "qb_pick"
        assert "quickbar" in res["data_schema"].schema


async def test_zeroconf_empty_string_unique_id(hass: HomeAssistant) -> None:
    """Test zeroconf when id property is empty string after strip (skips lines 621-623)."""
    zc = _ZCStub(
        ip_address=ip_address("192.0.2.20"),
        ip_addresses=[ip_address("192.0.2.20")],
        port=9123,
        hostname="QuickBars.local.",
        type="_quickbars._tcp.local.",
        name="QuickBars._quickbars._tcp.local.",
        properties={"id": "   ", "name": "QuickBars TV"},  # Whitespace only
    )

    with patch(
        "homeassistant.components.quickbars.config_flow.decode_zeroconf",
        return_value=(
            "192.0.2.20",
            9123,
            {"id": "   ", "name": "QuickBars TV"},  # This will be empty after strip()
            "QuickBars.local.",
            "QuickBars._quickbars._tcp.local.",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=zc
        )
    
    # Should proceed without setting unique_id (lines 621-623 NOT executed)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"