"""Tests for Elke27 sensors."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry



@dataclass(frozen=True, slots=True)
class PanelInfo:
    """Panel info snapshot stub."""

    mac: str
    name: str
    serial: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Snapshot stub."""

    panel_info: PanelInfo


class FakeHub:
    """Minimal hub stub for sensor tests."""

    def __init__(self) -> None:
        self.snapshot = Snapshot(
            panel_info=PanelInfo(
                mac="aa:bb:cc:dd:ee:ff",
                name="Panel A",
                serial="1234",
            )
        )
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

    def async_add_area_listener(self, listener):
        return self.async_add_listener(listener)

    def async_add_zone_listener(self, listener):
        return self.async_add_listener(listener)

    def async_add_output_listener(self, listener):
        return self.async_add_listener(listener)

    def fire_update(self) -> None:
        for listener in list(self._listeners):
            listener()

    @property
    def panel_info(self) -> PanelInfo:
        """Return panel info from the snapshot."""
        return self.snapshot.panel_info


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
            CONF_LINK_KEYS_JSON: {
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
    assert {"Panel A", "connected"} == {state.state for state in states}

    hub.snapshot = Snapshot(
        panel_info=PanelInfo(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel B",
            serial="1234",
        )
    )
    hub.is_ready = False
    hub.fire_update()
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert {"Panel B", "disconnected"} == {state.state for state in states}
