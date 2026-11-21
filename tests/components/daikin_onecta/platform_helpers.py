"""Helpers shared by platform tests."""

from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.client import OnectaClient
from daikin_onecta.models import GatewayDevice
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.daikin_onecta import OnectaDataUpdateCoordinator
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.core import HomeAssistant

from .conftest import FAKE_ACCESS_TOKEN

ALTHERMA_CLIMATE_ENTITY_ID = "climate.altherma_room_temperature"
ALTHERMA_CONTROL_MODE_SENSOR_ENTITY_ID = "sensor.altherma_control_mode"
ALTHERMA_WATER_HEATER_ENTITY_ID = "water_heater.altherma_domestic_hot_water_tank"
AIR_PURIFIER_ENTITY_ID = "fan.air_purifier"
ACCOUNT_REFRESH_BUTTON_ENTITY_ID = "button.daikin_onecta_account_refresh"

_FIXTURE_PATH = Path(__file__).parent / "fixtures"


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


def _load_gateway_devices(fixture: str) -> list[GatewayDevice]:
    """Load gateway devices from an archived cloud response."""
    fixture_data = json.loads((_FIXTURE_PATH / f"{fixture}.json").read_text())
    return [GatewayDevice.from_dict(device) for device in fixture_data]


async def _async_setup_fixture(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fixture: str,
    *,
    gateway_devices: list[GatewayDevice] | None = None,
) -> None:
    """Set up the integration using an archived cloud response."""
    if gateway_devices is None:
        gateway_devices = _load_gateway_devices(fixture)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
            new=AsyncMock(return_value=FAKE_ACCESS_TOKEN),
        ),
        patch(
            "homeassistant.components.daikin_onecta.coordinator."
            "OnectaClient.get_gateway_devices",
            new=AsyncMock(return_value=gateway_devices),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
