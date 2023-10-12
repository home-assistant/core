"""Tests for the Withings component."""
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.withings.const import DOMAIN
from homeassistant.components.withings.sensor import SENSORS
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import USER_ID

from tests.common import MockConfigEntry, async_fire_time_changed


async def async_get_entity_id(
    hass: HomeAssistant,
    key: str,
    user_id: int,
    platform: str,
) -> str | None:
    """Get an entity id for a user's attribute."""
    entity_registry = er.async_get(hass)
    unique_id = f"withings_{user_id}_{key}"

    return entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, polling_config_entry)

    for sensor in SENSORS:
        entity_id = await async_get_entity_id(hass, sensor.key, USER_ID, SENSOR_DOMAIN)
        assert hass.states.get(entity_id) == snapshot


async def test_update_failed(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    withings: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""
    await setup_integration(hass, polling_config_entry, False)

    withings.async_measure_get_meas.side_effect = Exception
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.henk_weight")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
