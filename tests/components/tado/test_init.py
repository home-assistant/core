"""Test the Tado integration."""

import asyncio
import time
from unittest.mock import patch

from homeassistant.components.tado import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.common import MockConfigEntry


async def test_v1_migration(hass: HomeAssistant) -> None:
    """Test migration from v1 to v2 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
        },
        unique_id="1",
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert CONF_USERNAME not in entry.data
    assert CONF_PASSWORD not in entry.data

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_asyncio_lock_serializes_updates(hass: HomeAssistant) -> None:
    """Test that the asyncio.Lock in TadoDataUpdateCoordinator serializes concurrent calls."""

    await async_init_integration(hass)
    entry = hass.config_entries.async_entries("tado")[0]
    coordinator = entry.runtime_data.coordinator

    timestamps: list = []

    def fake_get_me():
        timestamps.append(("start", time.monotonic()))
        time.sleep(0.2)
        timestamps.append(("end", time.monotonic()))
        return {"homes": [{"id": 1, "name": "Mocked Home"}]}

    # Patch all necessary coordinator calls to avoid real HTTP requests
    with (
        patch.object(coordinator._tado, "get_me", side_effect=fake_get_me),
        patch.object(coordinator._tado, "get_zones", return_value=[]),
        patch.object(coordinator._tado, "get_devices", return_value=[]),
        patch.object(coordinator, "_async_update_devices", return_value={}),
        patch.object(coordinator, "_async_update_zones", return_value={}),
        patch.object(
            coordinator,
            "_async_update_home",
            return_value={"weather": {}, "geofence": {}},
        ),
    ):
        await asyncio.gather(
            coordinator._async_update_data(),
            coordinator._async_update_data(),
        )

    end1 = timestamps[1][1]
    start2 = timestamps[2][1]

    assert start2 >= end1, (
        f"Second update started before first ended: start2={start2}, end1={end1}. "
    )


async def test_without_lock_allows_race_condition(hass: HomeAssistant) -> None:
    """Test that without a lock, concurrent updates may overlap (race condition)."""

    # I use this, to simulate a race condition and understand the behavior of the code
    class DummyCoordinator:
        """Mock coordinator without a lock to simulate race conditions."""

        def __init__(self) -> None:
            self.timestamps = []

        async def _async_update_data(self) -> None:
            self.timestamps.append(("start", time.monotonic()))
            await asyncio.sleep(0.2)
            self.timestamps.append(("end", time.monotonic()))

    coordinator = DummyCoordinator()

    await asyncio.gather(
        coordinator._async_update_data(),
        coordinator._async_update_data(),
    )

    starts = [t[1] for t in coordinator.timestamps if t[0] == "start"]
    ends = [t[1] for t in coordinator.timestamps if t[0] == "end"]

    starts.sort()
    ends.sort()

    assert starts[1] < ends[0], (
        f"Test failed: expected race condition but updates were serialized:\n"
        f"starts={starts}, ends={ends}"
    )
