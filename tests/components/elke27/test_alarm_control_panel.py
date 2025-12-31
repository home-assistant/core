"""Tests for Elke27 alarm control panel areas."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType
from unittest.mock import AsyncMock, patch

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

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


class FakeHub:
    """Minimal hub stub for area tests."""

    def __init__(self) -> None:
        self.panel_info = {"panel_name": "Panel A", "panel_mac": "aa:bb:cc:dd:ee:ff"}
        self.table_info = {"areas": 2}
        self.is_ready = True
        self.areas = [
            {"name": "Area 1", "state": "disarmed"},
            {"name": "Area 2", "state": "armed_away"},
        ]
        self._listeners: list[callable] = []

    async def async_start(self) -> None:
        return None

    async def async_stop(self) -> None:
        return None

    def async_add_listener(self, listener):
        self._listeners.append(listener)

        def _remove():
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def async_add_area_listener(self, listener):
        return self.async_add_listener(listener)

    def fire_update(self) -> None:
        for listener in list(self._listeners):
            listener()


async def test_area_entities_and_updates(hass: HomeAssistant) -> None:
    """Test area entities are created and update from snapshots."""
    hub = FakeHub()
    hub.async_start = AsyncMock()
    hub.async_stop = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.60",
            CONF_PORT: 2101,
            CONF_LINK_KEYS: {
                "tempkey_hex": "tk",
                "linkkey_hex": "lk",
                "linkhmac_hex": "lh",
            },
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.Elke27Hub", return_value=hub
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("alarm_control_panel")
    assert {state.state for state in states} == {"disarmed", "armed_away"}

    registry = er.async_get(hass)
    unique_ids = {
        entry.unique_id
        for entry in registry.entities.values()
        if entry.domain == "alarm_control_panel"
    }
    assert unique_ids == {"aa:bb:cc:dd:ee:ff_area_1", "aa:bb:cc:dd:ee:ff_area_2"}

    area_1 = next(
        entry
        for entry in registry.entities.values()
        if entry.unique_id == "aa:bb:cc:dd:ee:ff_area_1"
    )

    hub.areas[0]["state"] = "armed_home"
    hub.fire_update()
    await hass.async_block_till_done()

    state = hass.states.get(area_1.entity_id)
    assert state is not None
    assert state.state == "armed_home"
