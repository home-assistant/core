"""Tests for Elke27 diagnostics."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from types import ModuleType
from unittest.mock import Mock

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
class FakeClientConfig:
    """Minimal config stub."""


@dataclass(frozen=True, slots=True)
class FakeLinkKeys:
    """Minimal link keys stub."""

    payload: str

    @classmethod
    def from_json(cls, payload: str) -> "FakeLinkKeys":
        """Return stub link keys from JSON."""
        return cls(payload)


def redact_for_diagnostics(data: dict) -> dict:
    """Return a redacted diagnostics payload."""
    if not isinstance(data, dict):
        return {}
    redacted = {}
    for key, value in data.items():
        if key in {"access_code", "passphrase", "pin", "link_keys_json"}:
            continue
        if isinstance(value, dict):
            redacted[key] = redact_for_diagnostics(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_for_diagnostics(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


_elke27_lib.ClientConfig = FakeClientConfig
_elke27_lib.LinkKeys = FakeLinkKeys
_elke27_lib.Elke27Client = object
_elke27_lib.DiscoveredPanel = object
_elke27_lib.ArmMode = ArmMode
_elke27_lib.redact_for_diagnostics = redact_for_diagnostics

sys.modules["elke27_lib"] = _elke27_lib
sys.modules["elke27_lib.errors"] = _elke27_lib_errors

from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DOMAIN,
    MANUFACTURER_NUMBER,
)
from homeassistant.components.elke27.diagnostics import (
    async_get_config_entry_diagnostics,
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
    model: str
    firmware: str


@dataclass(frozen=True, slots=True)
class TableInfo:
    """Table info snapshot stub."""

    areas: int
    zones: int
    outputs: int


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Snapshot stub."""

    panel_info: PanelInfo
    table_info: TableInfo
    version: str
    updated_at: str
    access_code: str
    passphrase: str
    pin: str
    link_keys_json: str


async def test_diagnostics_redacts_sensitive_data(hass: HomeAssistant) -> None:
    """Test diagnostics redacts sensitive data and is JSON-safe."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.50",
            CONF_PORT: 2101,
            CONF_LINK_KEYS_JSON: "secret",
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    hub = Mock()
    hub.snapshot = Snapshot(
        panel_info=PanelInfo(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
            model="E27",
            firmware="1.2.3",
        ),
        table_info=TableInfo(areas=2, zones=4, outputs=2),
        version="2.0",
        updated_at="2024-01-01T00:00:00Z",
        access_code="1234",
        passphrase="secret",
        pin="9999",
        link_keys_json="raw",
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    json.dumps(diagnostics)
    assert diagnostics["manufacturer_number"] == MANUFACTURER_NUMBER
    assert diagnostics["integration_serial"] == "112233445566"
    assert diagnostics["link_keys_present"] is True
    assert diagnostics["snapshot_meta"]["version"] == "2.0"
    assert diagnostics["snapshot_meta"]["updated_at"] == "2024-01-01T00:00:00Z"
    assert diagnostics["snapshot"]["panel_info"]["name"] == "Panel A"
    assert "access_code" not in json.dumps(diagnostics)
    assert "passphrase" not in json.dumps(diagnostics)
    assert "pin" not in json.dumps(diagnostics)
    assert "link_keys_json" not in json.dumps(diagnostics)
