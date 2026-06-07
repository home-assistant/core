"""Test the Advantage Air Sensor Platform."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.components.advantage_air.sensor import (
    ADVANTAGE_AIR_SET_COUNTDOWN_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import add_mock_config

from tests.common import snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_get: AsyncMock,
) -> None:
    """Test sensor platform."""

    entry = await add_mock_config(hass, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_set_time_to(
    hass: HomeAssistant,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
) -> None:
    """Test the set_time_to action."""

    await add_mock_config(hass, [Platform.SENSOR])

    await hass.services.async_call(
        DOMAIN,
        "set_time_to",
        {
            ATTR_ENTITY_ID: ["sensor.myzone_time_to_on"],
            ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: 20,
        },
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_time_to",
        {
            ATTR_ENTITY_ID: ["sensor.myzone_time_to_off"],
            ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: 0,
        },
        blocking=True,
    )
    mock_update.assert_called_once()
