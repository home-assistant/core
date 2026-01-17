"""Tests for Elke27 sensors."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from types import ModuleType
from unittest.mock import AsyncMock, patch

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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


class AuthorizationRequired(Elke27Error):
    """Authorization required stub."""


class Elke27PermissionError(Elke27Error):
    """Permission error stub."""


class InvalidCredentials(Elke27AuthError):
    """Invalid credentials stub."""


class InvalidPin(Elke27AuthError):
    """Invalid PIN stub."""


class InvalidPinError(Elke27AuthError):
    """Invalid PIN error stub."""


class MissingPinError(Elke27AuthError):
    """Missing PIN error stub."""


_elke27_lib_errors.Elke27Error = Elke27Error
_elke27_lib_errors.Elke27ConnectionError = Elke27ConnectionError
_elke27_lib_errors.Elke27AuthError = Elke27AuthError
_elke27_lib_errors.Elke27TimeoutError = Elke27TimeoutError
_elke27_lib_errors.Elke27DisconnectedError = Elke27DisconnectedError
_elke27_lib_errors.Elke27LinkRequiredError = Elke27LinkRequiredError
_elke27_lib_errors.Elke27PinRequiredError = Elke27PinRequiredError
_elke27_lib_errors.AuthorizationRequired = AuthorizationRequired
_elke27_lib_errors.Elke27PermissionError = Elke27PermissionError
_elke27_lib_errors.InvalidCredentials = InvalidCredentials
_elke27_lib_errors.InvalidPin = InvalidPin
_elke27_lib_errors.InvalidPinError = InvalidPinError
_elke27_lib_errors.MissingPinError = MissingPinError


class ArmMode(Enum):
    """Stub arm modes."""

    DISARMED = "disarmed"
    ARMED_STAY = "armed_stay"
    ARMED_AWAY = "armed_away"
    ARMED_NIGHT = "armed_night"


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
