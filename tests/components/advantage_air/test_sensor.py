"""Test the Advantage Air Sensor Platform."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.advantage_air.const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from homeassistant.components.advantage_air.sensor import (
    ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
    ADVANTAGE_AIR_SET_COUNTDOWN_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config, assert_entities


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor platform."""

    entry = await add_mock_config(hass, [Platform.SENSOR])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    # Test First TimeToOn Sensor
    entity_id = "sensor.myzone_time_to_on"

    value = 20
    await hass.services.async_call(
        ADVANTAGE_AIR_DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {ATTR_ENTITY_ID: [entity_id], ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: value},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    # Test First TimeToOff Sensor
    entity_id = "sensor.myzone_time_to_off"

    value = 0
    await hass.services.async_call(
        ADVANTAGE_AIR_DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {ATTR_ENTITY_ID: [entity_id], ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: value},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()
