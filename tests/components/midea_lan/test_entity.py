"""Tests for midea_lan entity.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from midealocal.const import DeviceType

from homeassistant.components.midea_lan import entity as entity_module

from .conftest import DummyDevice


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
