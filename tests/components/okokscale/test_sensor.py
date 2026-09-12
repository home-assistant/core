"""Test the OKOK Scale sensors."""

from datetime import timedelta
import time

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.okokscale.const import DOMAIN
from homeassistant.const import ATTR_ASSUMED_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.util import dt as dt_util

from . import (
    OKOK_20_SERVICE_INFO,
    OKOK_C0_SERVICE_INFO,
    OKOK_F0_SERVICE_INFO,
    OKOK_F0_TITLE,
    conftest,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    inject_bluetooth_service_info_bleak,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


@pytest.mark.parametrize(
    "service_info",
    [
        OKOK_F0_SERVICE_INFO,
        OKOK_20_SERVICE_INFO,
        OKOK_C0_SERVICE_INFO,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    service_info: BluetoothServiceInfo,
) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=service_info.address)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 0

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sleepy_device_keeps_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the scale keeps its state and goes to assumed_state when idle."""
    start_monotonic = time.monotonic()
    entry = MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_SERVICE_INFO.address)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, OKOK_F0_SERVICE_INFO)
    await hass.async_block_till_done()

    mass_sensor = hass.states.get("sensor.okok_scale_2345_weight")
    assert mass_sensor.state == "85.2"
    assert mass_sensor.name == f"{OKOK_F0_TITLE} Weight"
    assert ATTR_ASSUMED_STATE not in mass_sensor.attributes

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

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

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Sleepy devices keep their last value and report assumed_state.
    mass_sensor = hass.states.get("sensor.okok_scale_2345_weight")
    assert mass_sensor.state == "85.2"
    assert mass_sensor.attributes[ATTR_ASSUMED_STATE] is True


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_bluetooth")
async def test_sensors_f0(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test receiving OKOK Scale F0 service info."""
    conftest.service_info = OKOK_F0_SERVICE_INFO
    entry = MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_SERVICE_INFO.address)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 0

    inject_bluetooth_service_info_bleak(hass, OKOK_F0_SERVICE_INFO)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
