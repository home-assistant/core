"""Test the Chef iQ sensors."""

from datetime import timedelta
import logging
import time

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import CHEFIQ_STATUS_SERVICE_INFO, CHEFIQ_TEMPERATURE_SERVICE_INFO


def _food_state(hass: HomeAssistant) -> str:
    state = hass.states.get("sensor.cq60_079a_food_temperature")
    assert state is not None
    return state.state


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
async def test_probe_unavailable_while_not_broadcasting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the sensors go unavailable, logged once, until the probe is seen again."""
    caplog.set_level(logging.INFO, logger="homeassistant.components.chef_iq")
    start_monotonic = time.monotonic()
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, CHEFIQ_TEMPERATURE_SERVICE_INFO)
    await hass.async_block_till_done()
    assert _food_state(hass) == "29.9"

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

    assert _food_state(hass) == STATE_UNAVAILABLE
    assert caplog.text.count("stopped broadcasting") == 1

    # The probe is seen again: the sensors recover and that is logged once too.
    inject_bluetooth_service_info(hass, CHEFIQ_TEMPERATURE_SERVICE_INFO)
    await hass.async_block_till_done()
    assert _food_state(hass) == "29.9"
    assert caplog.text.count("broadcasting again") == 1
