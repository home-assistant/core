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
from homeassistant.core import HomeAssistant

from .conftest import MockOnectaClient

ALTHERMA_CLIMATE_ENTITY_ID = "climate.altherma_room_temperature"
ALTHERMA_CONTROL_MODE_SENSOR_ENTITY_ID = "sensor.altherma_control_mode"
ALTHERMA_WATER_HEATER_ENTITY_ID = "water_heater.domestic_hot_water_tank"
AIR_PURIFIER_ENTITY_ID = "fan.air_purifier"

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


def _execute_typed_command(
    config_entry: MockConfigEntry, mock_onecta_client: MockOnectaClient
) -> AsyncMock:
    """Execute a typed command callback without making a cloud request."""
    coordinator = config_entry.runtime_data
    mock_onecta_client.patch_characteristic.reset_mock()
    mock_onecta_client.put_management_point.reset_mock()
    mock_onecta_client.install_firmware.reset_mock()

    async def execute(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        await command(coordinator.client)
        return True

    return AsyncMock(side_effect=execute)


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
            "homeassistant.components.daikin_onecta.coordinator."
            "OnectaClient.get_gateway_devices",
            new=AsyncMock(return_value=gateway_devices),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
