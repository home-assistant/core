"""Fixtures for Midea LAN tests."""

from collections.abc import Callable
from typing import Any

import pytest

from homeassistant.components.midea_lan.config_flow import MideaLanConfigFlow
from homeassistant.core import HomeAssistant


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

    def set_customize(self, value: str) -> None:
        """Record customize call."""
        self.calls.append(("set_customize", value))

    def set_ip_address(self, value: str) -> None:
        """Record ip address call."""
        self.calls.append(("set_ip_address", value))

    def open(self) -> None:
        """Record open call."""
        self.calls.append(("open",))

    def close(self) -> None:
        """Record close call."""
        self.calls.append(("close",))


@pytest.fixture
def mock_config_flow(hass: HomeAssistant) -> MideaLanConfigFlow:
    """Return a configured config flow instance."""
    config_flow = MideaLanConfigFlow()
    config_flow.hass = hass
    return config_flow
