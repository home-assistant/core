"""Tests for refoss_rpc sensor platform."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    mock_polling_rpc_update,
    mutate_rpc_device_status,
    register_entity,
    set_integration,
)


async def test_rpc_polling_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC polling sensor."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await set_integration(hass)

    assert hass.states.get(entity_id).state == "-30"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "wifi", "rssi", "-10")
    await mock_polling_rpc_update(hass, freezer)

    assert hass.states.get(entity_id).state == "-10"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-wifi-rssi"
