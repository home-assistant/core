"""Fixtures for Midea LAN tests."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from midealocal.const import DeviceType
import pytest

from homeassistant.components.midea_lan.const import CONF_KEY, CONF_SUBTYPE, DOMAIN
from homeassistant.const import CONF_NAME, CONF_TOKEN, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    BASE_DATA,
    TEST_DEVICE_ID,
    TEST_KEY,
    TEST_MODEL,
    TEST_NAME,
    TEST_SUBTYPE,
    TEST_TOKEN,
)

from tests.common import MockConfigEntry


class DummyDevice:
    """Shared fake Midea device for tests."""

    def __init__(
        self,
        device_type: int,
        *,
        attributes: dict | None = None,
    ) -> None:
        """Initialize fake device."""
        self.device_type = device_type
        self.device_id = TEST_DEVICE_ID
        self.name = TEST_NAME
        self.model = TEST_MODEL
        self.subtype = TEST_SUBTYPE
        self.available = False
        self.attributes = attributes or {}
        self._callbacks: list[Callable] = []
        self.calls: list[tuple] = []
        self.temperature_step = 1
        self.fan_modes = ["Low", "Medium", "High", "Auto"]
        self.modes = [
            "Auto",
            "ECO",
            "Sleep",
            "Anti-freezing",
            "Comfort",
            "Constant-temperature",
            "Normal",
            "Fast-heating",
            "Standby",
        ]

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

    def connect(self, check_protocol: bool = False) -> bool:
        """Record connect call and mirror midealocal's availability handling."""
        self.calls.append(("connect", check_protocol))
        self.available = check_protocol
        return check_protocol

    def open(self) -> None:
        """Record open call."""
        self.calls.append(("open",))

    def close(self) -> None:
        """Record close call."""
        self.calls.append(("close",))

    def close_socket(self) -> None:
        """Record close_socket call."""
        self.calls.append(("close_socket",))


def default_ac_device() -> DummyDevice:
    """Return a default AC device for tests."""
    return DummyDevice(
        DeviceType.AC,
        attributes={
            "power": True,
            "mode": 1,
            "target_temperature": 22.0,
            "indoor_temperature": 21.0,
            "fan_speed": 103,
            "swing_vertical": True,
            "swing_horizontal": True,
            "indoor_humidity": 50,
        },
    )


def entity_entries(
    hass: HomeAssistant, entry: MockConfigEntry
) -> dict[str, er.RegistryEntry]:
    """Return entity registry entries for a config entry, keyed by unique id."""
    entity_registry = er.async_get(hass)
    return {
        entity_entry.unique_id: entity_entry
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent loading the integration during config flow tests."""
    with patch(
        "homeassistant.components.midea_lan.async_setup_entry",
        return_value=True,
    ) as mock_entry:
        yield mock_entry


@pytest.fixture
def mock_config_entry() -> Callable[[DummyDevice], MockConfigEntry]:
    """Return a function that creates a mock config entry for a given device."""

    def _create(device: DummyDevice) -> MockConfigEntry:
        return MockConfigEntry(
            domain=DOMAIN,
            data={
                **BASE_DATA,
                CONF_TYPE: device.device_type,
                CONF_NAME: TEST_NAME,
                CONF_TOKEN: TEST_TOKEN,
                CONF_KEY: TEST_KEY,
                CONF_SUBTYPE: TEST_SUBTYPE,
            },
        )

    return _create
