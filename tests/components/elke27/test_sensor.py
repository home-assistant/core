"""Tests for Elke27 sensors."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType
from unittest.mock import AsyncMock, patch

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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


class FakeHub:
    """Minimal hub stub for sensor tests."""

    def __init__(self) -> None:
        self.panel_info = {"panel_name": "Panel A", "panel_mac": "aa:bb:cc:dd:ee:ff"}
        self.table_info = {"zones": 2}
        self.is_ready = True
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

    def fire_update(self) -> None:
        for listener in list(self._listeners):
            listener()


async def test_sensor_updates_from_hub(hass: HomeAssistant) -> None:
    """Test sensors reflect hub snapshot updates."""
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

    states = hass.states.async_all("sensor")
    assert len(states) == 2
    assert {"Panel A", "ready"} == {state.state for state in states}

    hub.panel_info["panel_name"] = "Panel B"
    hub.is_ready = False
    hub.fire_update()
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert {"Panel B", "not_ready"} == {state.state for state in states}
