"""Tests for midea_lan entity.py."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

from midealocal.const import DeviceType

from homeassistant.components.midea_lan import entity as entity_module


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
        self._updates: list[Callable] = self._callbacks

    def register_update(self, callback: Callable) -> None:
        """Record update callback registration."""
        self._callbacks.append(callback)


def test_midea_entity_basics_and_update_state() -> None:
    """Test MideaEntity properties and update_state branches."""
    dev = DummyDevice(DeviceType.AC, attributes={"legacy": 1, "available": True})
    ent = entity_module.MideaEntity(dev, "legacy")

    assert ent.unique_id.endswith("legacy")
    assert ent.should_poll is False
    assert ent.available is True
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


async def test_async_added_to_hass_registers_callback() -> None:
    """Test async_added_to_hass registers the update callback."""
    dev = DummyDevice(DeviceType.AC)
    ent = entity_module.MideaEntity(dev, "k")

    await ent.async_added_to_hass()

    assert ent.update_state in dev._callbacks


async def test_async_will_remove_from_hass_unregisters_callback() -> None:
    """Test async_will_remove_from_hass removes the update callback."""
    dev = DummyDevice(DeviceType.AC)
    ent = entity_module.MideaEntity(dev, "k")
    await ent.async_added_to_hass()
    await ent.async_will_remove_from_hass()
    assert ent.update_state not in dev._updates
