"""Fixtures for iZone integration tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

from pizone import Controller, Zone
import pytest

from homeassistant.components.izone.const import IZONE

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
async def mock_discovery(
    mock_controller: AsyncMock, mock_zones: list[AsyncMock]
) -> AsyncGenerator[AsyncMock]:
    """Create a mock discovery service with one controller and zones."""
    mock_controller.zones = mock_zones
    with patch(
        "homeassistant.components.izone.discovery.pizone.discovery", autospec=True
    ) as mock_disco:
        mock_disco.return_value.start_discovery = AsyncMock()
        mock_disco.return_value.controllers = {
            mock_controller.device_uid: mock_controller
        }
        yield mock_disco


@pytest.fixture
async def mock_zones() -> list[AsyncMock]:
    """Create a list of mock zones."""
    return [create_mock_zone(index=0, name="Living Room")]


@pytest.fixture
async def mock_controller(mock_zones: list[AsyncMock]) -> AsyncMock:
    """Create a mock controller."""
    return create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=1,
        zones_total=1,
    )
