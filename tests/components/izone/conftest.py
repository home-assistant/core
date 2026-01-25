"""Fixtures for iZone integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from pizone import Controller, Zone
import pytest

from homeassistant.components.izone.const import (
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCOVERED,
    IZONE,
)
from homeassistant.components.izone.discovery import DiscoveryService
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for iZone."""
    return MockConfigEntry(
        domain=IZONE,
        title="iZone",
        data={},
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_pizone_discovery_service() -> Mock:
    """Create a mock pizone discovery service."""
    disco = Mock()
    disco.controllers = {}
    disco.start_discovery = AsyncMock()
    disco.close = AsyncMock()
    return disco


def create_mock_controller(
    device_uid: str = "test_controller_123",
    sys_type: str = "iZone310",
    zones_total: int = 4,
    zone_ctrl: int = 1,
    ras_mode: str = "master",
    free_air_enabled: bool = False,
    zones: list[Zone] | None = None,
) -> Mock:
    """Create a mock Controller with configurable parameters."""
    controller = Mock(spec=Controller)
    controller.device_uid = device_uid
    controller.sys_type = sys_type
    controller.zones_total = zones_total
    controller.zone_ctrl = zone_ctrl
    controller.ras_mode = ras_mode
    controller.free_air_enabled = free_air_enabled
    controller.free_air = False
    controller.is_on = True
    controller.mode = Controller.Mode.COOL
    controller.temp_setpoint = 24.0
    controller.temp_return = 22.0
    controller.temp_supply = 16.0
    controller.temp_min = 15.0
    controller.temp_max = 30.0
    controller.fan = Controller.Fan.MED
    controller.fan_modes = [
        Controller.Fan.LOW,
        Controller.Fan.MED,
        Controller.Fan.HIGH,
        Controller.Fan.AUTO,
    ]
    controller.zones = zones if zones is not None else []
    return controller


def create_mock_zone(
    index: int = 0,
    name: str = "Zone",
    temp_current: float | None = 22.5,
    temp_setpoint: float = 24.0,
) -> Mock:
    """Create a mock Zone with configurable parameters."""
    zone = Mock(spec=Zone)
    zone.index = index
    zone.name = name
    zone.type = Zone.Type.AUTO
    zone.mode = Zone.Mode.AUTO
    zone.temp_current = temp_current
    zone.temp_setpoint = temp_setpoint
    zone.airflow_min = 0
    zone.airflow_max = 100
    zone.is_on = True
    return zone


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
) -> Generator[callable]:
    """Set up iZone integration with mocked discovery service."""

    async def _setup(
        config_entry: MockConfigEntry,
        mock_pizone_disco: Mock,
    ) -> Mock:
        """Set up the integration with provided mocks."""

        async def mock_start_discovery(hass: HomeAssistant) -> DiscoveryService:
            # Create a real DiscoveryService but inject mock pizone disco
            disco = DiscoveryService(hass)
            disco.pi_disco = mock_pizone_disco
            hass.data[DATA_DISCOVERY_SERVICE] = disco
            return disco

        with (
            patch(
                "homeassistant.components.izone.async_start_discovery_service",
                side_effect=mock_start_discovery,
            ),
            patch(
                "homeassistant.components.izone.discovery.pizone.discovery",
                return_value=mock_pizone_disco,
            ),
        ):
            config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

            # Trigger controller discovered for each controller in the mock disco
            for controller in mock_pizone_disco.controllers.values():
                async_dispatcher_send(hass, DISPATCH_CONTROLLER_DISCOVERED, controller)

            await hass.async_block_till_done()

        return mock_pizone_disco

    return _setup
