"""Helpers shared by platform tests."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from daikin_onecta.client import OnectaClient
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.daikin_onecta import OnectaDataUpdateCoordinator
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.core import HomeAssistant

ALTHERMA_CLIMATE_ENTITY_ID = "climate.altherma_room_temperature"
ALTHERMA_CONTROL_MODE_SENSOR_ENTITY_ID = "sensor.altherma_control_mode"


async def _async_fire_coordinator_update(
    hass: HomeAssistant,
    coordinator: OnectaDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Advance time until the coordinator's next scheduled update."""
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _execute_typed_command(config_entry: MockConfigEntry) -> AsyncMock:
    """Execute a typed command callback without making a cloud request."""
    coordinator = config_entry.runtime_data
    coordinator.client.patch_characteristic = AsyncMock()
    coordinator.client.put_management_point = AsyncMock()
    coordinator.client.install_firmware = AsyncMock()

    async def execute(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        await command(coordinator.client)
        return True

    return AsyncMock(side_effect=execute)


def _mock_coordinator(device: DaikinOnectaDevice) -> MagicMock:
    """Create a coordinator mock containing the supplied gateway wrapper."""
    coordinator = MagicMock()
    coordinator.data = {device.id: device}
    return coordinator
