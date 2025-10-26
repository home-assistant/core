"""Common fixtures for the Sony Projector tests."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest


class _FakeProjector:
    """Lightweight stub for the pysdcp Projector class used in tests."""

    def __init__(self, host: str) -> None:
        self.host = host
        self._power = False

    def get_power(self) -> bool:
        """Return the simulated power state."""

        return self._power

    def set_power(self, powered: bool) -> bool:
        """Store the simulated power state and report success."""

        self._power = powered
        return True


_FAKE_PYSDCP = ModuleType("pysdcp")
_FAKE_PYSDCP.Projector = _FakeProjector
sys.modules.setdefault("pysdcp", _FAKE_PYSDCP)


@pytest.fixture(autouse=True)
def stub_pysdcp_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Ensure the stub pysdcp module is present for each test."""

    monkeypatch.setitem(sys.modules, "pysdcp", _FAKE_PYSDCP)
    return _FAKE_PYSDCP
