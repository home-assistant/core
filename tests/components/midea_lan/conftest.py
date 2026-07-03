"""Fixtures for Midea LAN tests."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


class DummyDevice:
    """Shared fake Midea device for tests."""

    def __init__(
        self,
        device_type: int,
        *,
        attributes: dict | None = None,
        available: bool = True,
    ) -> None:
        """Initialize fake device."""
        self.device_type = device_type
        self.device_id = 123
        self.name = "Dummy"
        self.model = "M1"
        self.subtype = 7
        self.available = available
        self.attributes = attributes or {}
        self._callbacks: list[Callable] = []
        self.calls: list[tuple] = []
        self.temperature_step = 1
        self.fan_modes = ["low", "high"]
        self.modes = ["comfort", "eco"]

    def register_update(self, callback: Callable) -> None:
        """Record update callback registration."""
        self._callbacks.append(callback)

    def unregister_update(self, callback: Callable) -> None:
        """Record update callback removal."""
        self._callbacks.remove(callback)

    def notify_update(self, status: dict[str, Any]) -> None:
        """Notify all registered callbacks with new state."""
        for callback in self._callbacks.copy():
            callback(status)

    def get_attribute(self, attr: str) -> Any:
        """Return attribute value."""
        return self.attributes.get(attr)

    def set_attribute(self, attr: str, value: Any) -> None:
        """Record set attribute call."""
        self.calls.append(("set_attribute", attr, value))

    def set_target_temperature(self, **kwargs: Any) -> None:
        """Record set target temperature call."""
        self.calls.append(("set_target_temperature", kwargs))

    def set_swing(self, **kwargs: Any) -> None:
        """Record set swing call."""
        self.calls.append(("set_swing", kwargs))

    def set_mode(self, zone: int, mode: int) -> None:
        """Record set mode call."""
        self.calls.append(("set_mode", zone, mode))

    def open(self) -> None:
        """Record open call."""
        self.calls.append(("open",))

    def close(self) -> None:
        """Record close call."""
        self.calls.append(("close",))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent loading the integration during config flow tests."""
    with patch(
        "homeassistant.components.midea_lan.async_setup_entry",
        return_value=True,
    ) as mock_entry:
        yield mock_entry
