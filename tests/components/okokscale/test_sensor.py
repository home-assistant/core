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
    OKOK_20_ADDRESS,
    OKOK_20_SERVICE_INFO,
    OKOK_C0_ADDRESS,
    OKOK_C0_SERVICE_INFO,
    OKOK_F0_ADDRESS,
    OKOK_F0_SERVICE_INFO,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


@pytest.mark.parametrize(
    ("mock_config_entry", "service_info", "enity_id_base", "weight", "signal_strength"),
    [
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_ADDRESS),
            OKOK_F0_SERVICE_INFO,
            "sensor.okok_scale_2345",
            85.2,
            -60,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_20_ADDRESS),
            OKOK_20_SERVICE_INFO,
            "sensor.okok_scale_89ab",
            53.1,
            -61,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_C0_ADDRESS),
            OKOK_C0_SERVICE_INFO,
            "sensor.okok_scale_cdef",
            160.8,
            -62,
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    service_info: BluetoothServiceInfo,
    enity_id_base: str,
    weight: float,
    signal_strength: int,
) -> None:
    """Test setting up creates the sensors."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.states.async_all("sensor")

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    state = hass.states.get(f"{enity_id_base}_weight")
    assert state is not None
    assert state.state == str(weight)

    state = hass.states.get(f"{enity_id_base}_signal_strength")
    assert state is not None
    assert state.state == str(signal_strength)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sleepy_device_keeps_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the scale keeps its state and goes to assumed_state when idle."""
    start_monotonic = time.monotonic()
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, OKOK_F0_SERVICE_INFO)
    await hass.async_block_till_done()
    mass = hass.states.get("sensor.okok_scale_2345_weight")
    assert mass.state == "85.2"
    assert ATTR_ASSUMED_STATE not in mass.attributes

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
    mass = hass.states.get("sensor.okok_scale_2345_weight")
    assert mass.state == "85.2"
    assert mass.attributes[ATTR_ASSUMED_STATE] is True
