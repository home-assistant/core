"""Test the Chef iQ sensors."""

from datetime import timedelta
import time

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.const import ATTR_ASSUMED_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import CHEFIQ_STATUS_SERVICE_INFO, CHEFIQ_TEMPERATURE_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up creates the sensors from the rotating packet types."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.states.async_all("sensor")

    # The temperature packet creates the six temperatures (plus signal strength);
    # the status packet adds battery and SoC temperature.
    inject_bluetooth_service_info(hass, CHEFIQ_TEMPERATURE_SERVICE_INFO)
    await hass.async_block_till_done()
    inject_bluetooth_service_info(hass, CHEFIQ_STATUS_SERVICE_INFO)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sleepy_device_keeps_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the probe keeps its state and goes to assumed_state when idle."""
    start_monotonic = time.monotonic()
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, CHEFIQ_TEMPERATURE_SERVICE_INFO)
    await hass.async_block_till_done()
    food = hass.states.get("sensor.cq60_079a_food_temperature")
    assert food.state == "29.9"
    assert ATTR_ASSUMED_STATE not in food.attributes

    # Fast-forward past the stale-advertisement window with no advertisements.
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    with (
        patch_bluetooth_time(monotonic_now),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    # Sleepy devices keep their last value and report assumed_state.
    food = hass.states.get("sensor.cq60_079a_food_temperature")
    assert food.state == "29.9"
    assert food.attributes[ATTR_ASSUMED_STATE] is True
