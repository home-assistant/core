"""Tests for midea_lan entity.py."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, patch

from midealocal.const import DeviceType

from homeassistant.components.midea_lan import entity as entity_module
from homeassistant.const import Platform


class DummyDevice:
    """Simple fake Midea device for entity tests."""

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

    def register_update(self, callback: Callable) -> None:
        """Record update callback registration."""
        self._callbacks.append(callback)


def _device_map() -> dict:
    """Return minimal MIDEA_DEVICES map used by entity tests."""
    return {
        DeviceType.AC: {
            "name": "AC",
            "entities": {
                "legacy": {
                    "type": Platform.CLIMATE,
                    "name": "Legacy",
                    "icon": "mdi:air-conditioner",
                    "has_entity_name": False,
                },
                "named": {
                    "type": Platform.CLIMATE,
                    "name": None,
                    "translation_key": "named",
                    "has_entity_name": True,
                    "icon": "mdi:air-conditioner",
                },
            },
        },
    }


def test_midea_entity_basics_and_update_state() -> None:
    """Test MideaEntity properties and update_state branches."""
    dev = DummyDevice(DeviceType.AC, attributes={"legacy": 1, "available": True})

    with patch.object(entity_module, "MIDEA_DEVICES", _device_map()):
        ent = entity_module.MideaEntity(dev, "legacy")

    assert ent.unique_id.endswith("legacy")
    assert ent.should_poll is False
    assert ent.available is True
    assert ent.icon == "mdi:air-conditioner"
    assert ent.device_info["manufacturer"] == "Midea"

    ent.schedule_update_ha_state = MagicMock()
    ent.hass = None
    ent.update_state({"legacy": 1})
    ent.schedule_update_ha_state.assert_not_called()

    ent.hass = MagicMock(is_stopping=True)
    ent.update_state({"legacy": 1})
    ent.schedule_update_ha_state.assert_not_called()

    ent.hass = MagicMock(is_stopping=False)
    ent.update_state({"legacy": 1})
    ent.schedule_update_ha_state.assert_called_once()


def test_midea_entity_has_name_branch() -> None:
    """Test has_entity_name=True and name=None branch."""
    dev = DummyDevice(DeviceType.AC)
    with patch.object(entity_module, "MIDEA_DEVICES", _device_map()):
        ent = entity_module.MideaEntity(dev, "named")
    assert ent.name is None
