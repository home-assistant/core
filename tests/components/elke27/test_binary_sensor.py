"""Tests for Elke27 zone binary sensors."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, patch

_client_module = ModuleType("elke27_lib.client")
_client_module.Elke27Client = object
_client_module.Result = object
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
    """Minimal hub stub for zone tests."""

    def __init__(self) -> None:
        self.panel_info = {"panel_name": "Panel A", "panel_mac": "aa:bb:cc:dd:ee:ff"}
        self.table_info = {"zones": 2}
        self.is_ready = True
        self.zones = [
            {"name": "Front Door", "state": "open"},
            {"name": "Garage", "state": "closed"},
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

    def async_add_zone_listener(self, listener):
        return self.async_add_listener(listener)

    def fire_update(self) -> None:
        for listener in list(self._listeners):
            listener()


async def test_zone_entities_and_updates(hass: HomeAssistant) -> None:
    """Test zone entities are created and update from snapshots."""
    hub = FakeHub()
    hub.async_start = AsyncMock()
    hub.async_stop = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.60",
            CONF_PORT: 2101,
            CONF_LINK_KEYS: {"link_key": "lk", "link_hmac": "lh"},
            CONF_INTEGRATION_SERIAL: "11:22:33:44:55:66",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.elke27.Elke27Hub", return_value=hub
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("binary_sensor")
    assert {state.state for state in states} == {"on", "off"}

    registry = er.async_get(hass)
    unique_ids = {
        entry.unique_id
        for entry in registry.entities.values()
        if entry.domain == "binary_sensor"
    }
    assert unique_ids == {"aa:bb:cc:dd:ee:ff_zone_1", "aa:bb:cc:dd:ee:ff_zone_2"}

    zone_1 = next(
        entry
        for entry in registry.entities.values()
        if entry.unique_id == "aa:bb:cc:dd:ee:ff_zone_1"
    )

    hub.zones[0]["state"] = "closed"
    hub.fire_update()
    await hass.async_block_till_done()

    state = hass.states.get(zone_1.entity_id)
    assert state is not None
    assert state.state == "off"
