"""Test fixtures for the Kii Audio integration."""

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from homeassistant.components.kii_audio.const import KII_CONTROL_PRODUCT_ID

SYSTEM_ID = "system-id"
ZONE_ID = "zone-id"


def make_zone(
    *,
    advanced_mode: bool = False,
    has_kii_control: bool = False,
    source: str = "analog",
) -> dict[str, Any]:
    """Return a sample Kii zone payload."""
    devices = (
        [{"deviceId": "control", "productId": KII_CONTROL_PRODUCT_ID}]
        if has_kii_control
        else []
    )
    return {
        "zoneId": ZONE_ID,
        "settings": {
            "zoneName": "Office",
            "advancedMode": advanced_mode,
            "power": True,
            "audio": {
                "volume": -50.0,
                "mute": False,
                "source": source,
                "analogHighSensitivity": False,
                "latency": "optimum",
                "toneControl": {
                    "enabled": True,
                    "low": {"gain": 1.2, "frequency": 120.0},
                    "high": {"gain": -0.8, "frequency": 3000.0},
                },
            },
        },
        "devices": [
            {
                "deviceId": "speaker-1",
                "modelName": "Kii Seven",
                "macAddress": "00:11:22:33:44:55",
            },
        ],
        "kiilink": {"devices": devices},
    }


class FakeCoordinator:
    """Minimal coordinator for entity unit tests."""

    def __init__(self, zone: dict[str, Any]) -> None:
        """Initialize the fake coordinator."""
        self.data = {"systemName": "Kii System", "zones": [zone]}
        self.config_entry = SimpleNamespace(
            unique_id=SYSTEM_ID,
            entry_id="entry-id",
            title="Kii System",
        )
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def async_add_listener(self, *_args: Any, **_kwargs: Any) -> Any:
        """Return a dummy unsubscribe callback."""
        return lambda: None

    async def async_set_zone_setting(
        self, zone_id: str, setting: str, value: Any
    ) -> None:
        """Record a generic zone setting request."""
        self.calls.append(("setting", (zone_id, setting, value)))

    async def async_set_zone_volume(self, zone_id: str, volume: float) -> None:
        """Record a volume request."""
        self.calls.append(("volume", (zone_id, volume)))

    async def async_set_zone_mute(self, zone_id: str, mute: bool) -> None:
        """Record a mute request."""
        self.calls.append(("mute", (zone_id, mute)))

    async def async_set_zone_power(self, zone_id: str, power: bool) -> None:
        """Record a power request."""
        self.calls.append(("power", (zone_id, power)))

    async def async_set_zone_source(self, zone_id: str, source: str) -> None:
        """Record a source request."""
        self.calls.append(("source", (zone_id, source)))


@pytest.fixture
def zone() -> dict[str, Any]:
    """Return a mutable sample zone."""
    return make_zone()


@pytest.fixture
def coordinator(zone: dict[str, Any]) -> FakeCoordinator:
    """Return a fake coordinator backed by the sample zone."""
    return FakeCoordinator(deepcopy(zone))
