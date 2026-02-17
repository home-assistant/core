"""Tests for Fritz!Tools sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from fritzconnection.core.exceptions import FritzConnectionException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz.const import DOMAIN, SCAN_INTERVAL, UPTIME_DEVIATION
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_FB_SERVICES, MOCK_USER_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.freeze_time(datetime(2024, 9, 1, 20, tzinfo=UTC))
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
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
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test failed update of Fritz!Tools sensors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    fc_class_mock().call_action_side_effect(FritzConnectionException("Boom"))

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error while updating the data: Boom" in caplog.text

    sensors = hass.states.async_all(SENSOR_DOMAIN)
    for sensor in sensors:
        assert sensor.state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2026-02-14T09:30:00+00:00")
async def test_sensor_uptime_spike(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test handling of uptime spikes in Fritz!Tools sensors."""

    entity_id = "sensor.mock_title_last_restart"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == "2026-01-16T06:00:21+00:00"

    # Simulate uptime spike by setting uptime to a value between
    # the previous one and a delta smaller than UPTIME_DEVIATION
    base_uptime = MOCK_FB_SERVICES["DeviceInfo1"]["GetInfo"]["NewUpTime"]
    update_uptime = {
        "DeviceInfo1": {
            "GetInfo": {
                "NewUpTime": base_uptime + SCAN_INTERVAL - UPTIME_DEVIATION + 1,
            },
        },
    }
    fc_class_mock().override_services({**MOCK_FB_SERVICES, **update_uptime})

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (new_state := hass.states.get(entity_id))
    assert new_state.state == "2026-01-16T06:00:21+00:00"
