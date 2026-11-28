"""Test the Threema Gateway sensor platform."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.threema.client import ThreemaConnectionError
from homeassistant.components.threema.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_CREDITS, MOCK_GATEWAY_ID

ENTITY_ID = "sensor.threema_testgwy_remaining_credits"


async def test_credits_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the credits sensor of the gateway."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == str(MOCK_CREDITS)

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{MOCK_GATEWAY_ID}_credits"
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC

    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.identifiers == {("threema", MOCK_GATEWAY_ID)}
    assert device.name == mock_config_entry.title
    assert device.model == "Gateway"


async def test_credits_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_credentials: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the credits sensor follows the gateway and its availability."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_credentials.return_value = 42
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "42"

    mock_credentials.side_effect = ThreemaConnectionError("Connection refused")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert [
        record.levelno
        for record in caplog.records
        if "is unavailable" in record.message
    ] == [logging.INFO]

    mock_credentials.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "42"
