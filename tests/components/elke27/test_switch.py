"""Tests for Elke27 zone bypass switches."""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from enum import Enum
from types import ModuleType
from unittest.mock import AsyncMock, patch

import pytest

_elke27_lib = ModuleType("elke27_lib")
_elke27_lib_errors = ModuleType("elke27_lib.errors")


class Elke27Error(Exception):
    """Base Elke27 error."""


class Elke27ConnectionError(Elke27Error):
    """Connection error stub."""


class Elke27AuthError(Elke27Error):
    """Auth error stub."""


class Elke27TimeoutError(Elke27Error):
    """Timeout error stub."""


class Elke27DisconnectedError(Elke27Error):
    """Disconnected error stub."""


class Elke27LinkRequiredError(Elke27Error):
    """Link required stub."""


class Elke27PinRequiredError(Elke27Error):
    """PIN required stub."""


_elke27_lib_errors.Elke27Error = Elke27Error
_elke27_lib_errors.Elke27ConnectionError = Elke27ConnectionError
_elke27_lib_errors.Elke27AuthError = Elke27AuthError
_elke27_lib_errors.Elke27TimeoutError = Elke27TimeoutError
_elke27_lib_errors.Elke27DisconnectedError = Elke27DisconnectedError
_elke27_lib_errors.Elke27LinkRequiredError = Elke27LinkRequiredError
_elke27_lib_errors.Elke27PinRequiredError = Elke27PinRequiredError


class ArmMode(Enum):
    """Stub arm modes."""

    AWAY = "away"
    STAY = "stay"
    NIGHT = "night"
    VACATION = "vacation"
    INSTANT = "instant"


@dataclass(frozen=True, slots=True)
class FakeLinkKeys:
    """Minimal link keys stub."""

    payload: str

    @classmethod
    def from_json(cls, payload: str) -> "FakeLinkKeys":
        """Return stub link keys from JSON."""
        return cls(payload)


@dataclass(frozen=True, slots=True)
class FakeClientConfig:
    """Minimal config stub."""


_elke27_lib.ClientConfig = FakeClientConfig
_elke27_lib.LinkKeys = FakeLinkKeys
_elke27_lib.Elke27Client = object
_elke27_lib.DiscoveredPanel = object
_elke27_lib.ArmMode = ArmMode

sys.modules["elke27_lib"] = _elke27_lib
sys.modules["elke27_lib.errors"] = _elke27_lib_errors

from homeassistant.components.elke27 import switch as switch_module
from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@dataclass(frozen=True, slots=True)
class PanelInfo:
    """Panel info snapshot stub."""

    mac: str
    name: str
    serial: str


@dataclass(frozen=True, slots=True)
class ZoneState:
    """Zone state stub."""

    zone_id: int
    name: str
    bypassed: bool
    definition: str = "NORMAL"


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Snapshot stub."""

    panel_info: PanelInfo
    zones: list[ZoneState]


class FakeHub:
    """Minimal hub stub for zone bypass tests."""

    def __init__(self) -> None:
        self.snapshot = Snapshot(
            panel_info=PanelInfo(
                mac="aa:bb:cc:dd:ee:ff",
                name="Panel A",
                serial="1234",
            ),
            zones=[
                ZoneState(zone_id=1, name="Front Door", bypassed=False),
                ZoneState(zone_id=2, name="Back Door", bypassed=True),
            ],
        )
        self.is_ready = True
        self._listeners: list[callable] = []
        self.async_set_zone_bypass = AsyncMock(return_value=True)

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

    @property
    def panel_info(self) -> PanelInfo:
        """Return panel info from the snapshot."""
        return self.snapshot.panel_info

    def fire_update(self) -> None:
        for listener in list(self._listeners):
            listener()


async def test_zone_bypass_switches_update_and_actions(
    hass: HomeAssistant,
) -> None:
    """Test zone bypass switches are created, update, and delegate actions."""
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

    states = hass.states.async_all("switch")
    assert {state.state for state in states} == {"on", "off"}

    registry = er.async_get(hass)
    unique_ids = {
        entry.unique_id
        for entry in registry.entities.values()
        if entry.domain == "switch"
    }
    assert unique_ids == {
        "aa:bb:cc:dd:ee:ff_zone_1_bypass",
        "aa:bb:cc:dd:ee:ff_zone_2_bypass",
    }

    zone_1 = next(
        entry
        for entry in registry.entities.values()
        if entry.unique_id == "aa:bb:cc:dd:ee:ff_zone_1_bypass"
    )

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": zone_1.entity_id},
        blocking=True,
    )
    hub.async_set_zone_bypass.assert_awaited_once_with(1, True)
    assert hub.snapshot.zones[0].bypassed is False

    updated = replace(hub.snapshot.zones[0], bypassed=True)
    hub.snapshot = replace(
        hub.snapshot, zones=[updated, hub.snapshot.zones[1]]
    )
    hub.fire_update()
    await hass.async_block_till_done()

    state = hass.states.get(zone_1.entity_id)
    assert state is not None
    assert state.state == "on"


async def test_zone_bypass_pin_required(hass: HomeAssistant) -> None:
    """Test PIN-required error surfaces as HomeAssistantError."""
    hub = FakeHub()
    hub.async_start = AsyncMock()
    hub.async_stop = AsyncMock()
    hub.async_set_zone_bypass.side_effect = switch_module.Elke27PinRequiredError

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.61",
            CONF_PORT: 2101,
            CONF_LINK_KEYS_JSON: {"tempkey_hex": "tk"},
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.elke27.Elke27Hub", return_value=hub):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    zone_1 = next(
        entry
        for entry in registry.entities.values()
        if entry.unique_id == "aa:bb:cc:dd:ee:ff_zone_1_bypass"
    )

    with pytest.raises(HomeAssistantError, match="PIN required to perform this action."):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": zone_1.entity_id},
            blocking=True,
        )
