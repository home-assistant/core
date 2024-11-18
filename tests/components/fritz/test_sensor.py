"""Tests for Fritz!Tools sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fritzconnection.core.exceptions import FritzConnectionException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.freeze_time(datetime(2024, 9, 1, 20, tzinfo=UTC))
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of Fritz!Tools sensors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_update_fail(
    hass: HomeAssistant, fc_class_mock, fh_class_mock
) -> None:
    """Test failed update of Fritz!Tools sensors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    fc_class_mock().call_action_side_effect(FritzConnectionException)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=300))
    await hass.async_block_till_done(wait_background_tasks=True)

    sensors = hass.states.async_all(SENSOR_DOMAIN)
    for sensor in sensors:
        assert sensor.state == STATE_UNAVAILABLE
