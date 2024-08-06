"""Tests for the registry."""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import storage
from homeassistant.helpers.registry import SAVE_DELAY, SAVE_DELAY_LONG, BaseRegistry

from tests.common import async_fire_time_changed


class SampleRegistry(BaseRegistry):
    """Class to hold a registry of X."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the registry."""
        self.hass = hass
        self._store = storage.Store(hass, 1, "test")
        self.save_calls = 0

    def _data_to_save(self) -> dict[str, Any]:
        """Return data of registry to save."""
        self.save_calls += 1
        return {}


@pytest.mark.parametrize(
    "long_delay_state",
    [
        CoreState.not_running,
        CoreState.starting,
        CoreState.stopped,
        CoreState.final_write,
    ],
)
async def test_async_schedule_save(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    long_delay_state: CoreState,
    hass_storage: dict[str, Any],
) -> None:
    """Test saving the registry.

    If CoreState is not running, it should save with long delay.

    Storage will always save at final write if there is a
    write pending so we should not schedule a save in that case.
    """
    registry = SampleRegistry(hass)
    hass.set_state(long_delay_state)

    registry.async_schedule_save()
    freezer.tick(SAVE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert registry.save_calls == 0

    freezer.tick(SAVE_DELAY_LONG)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert registry.save_calls == 1

    hass.set_state(CoreState.running)
    registry.async_schedule_save()
    freezer.tick(SAVE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert registry.save_calls == 2
