"""Fixtures for iZone integration tests."""

from collections.abc import AsyncGenerator, Generator, Iterable
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

from pizone import Controller, Zone
import pytest

from homeassistant.components.izone import discovery as izone_discovery
from homeassistant.components.izone.const import DATA_DISCOVERY_SERVICE, DOMAIN
from homeassistant.const import CONF_EXCLUDE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for iZone."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="iZone",
        data={},
        entry_id="test_entry_id",
        unique_id="000000001",
        version=2,
    )


@pytest.fixture
def mock_pizone_discovery_service() -> Mock:
    """Create a mock pizone discovery service."""
    disco = Mock()
    disco.fetch_controllers = AsyncMock(return_value={})
    disco.start_discovery = AsyncMock()
    disco.close = AsyncMock()
    return disco


def create_mock_controller(
    device_uid: str = "000000001",
    device_ip: str = "192.0.2.1",
    sys_type: str = "iZone310",
    zones_total: int = 4,
    zone_ctrl: int = 1,
    ras_mode: str = "master",
    free_air_enabled: bool = False,
) -> Mock:
    """Create a mock Controller with configurable parameters."""
    controller = Mock(spec=Controller)
    controller.device_uid = device_uid
    controller.device_ip = device_ip
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


def create_mock_discovery_service(*controllers: Mock) -> Mock:
    """Create a mock discovery service with the given controllers."""
    service = Mock()
    service.pi_disco = Mock()
    service.pi_disco.controllers = {c.device_uid: c for c in controllers}
    service.pi_disco.fetch_controller = AsyncMock(
        side_effect=lambda uid, timeout=None: service.pi_disco.controllers.get(uid)
    )
    service.pi_disco.fetch_controllers = AsyncMock(
        side_effect=lambda timeout=None: dict(service.pi_disco.controllers)
    )
    service.async_schedule_idle_stop = Mock()
    return service


@contextmanager
def patch_discovered_controllers(
    controllers: Mock | dict[str, Mock] | Iterable[Mock],
) -> Generator[Mock]:
    """Patch discovery startup so async_discover_controllers uses these controllers."""
    if isinstance(controllers, dict):
        ctrl_list = list(controllers.values())
    elif isinstance(controllers, Mock):
        ctrl_list = [controllers]
    else:
        ctrl_list = list(controllers)
    service = create_mock_discovery_service(*ctrl_list)
    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        new_callable=AsyncMock,
        return_value=service,
    ):
        yield service


async def async_load_yaml_exclude(hass: HomeAssistant, *uids: str) -> None:
    """Load deprecated YAML exclude config through the integration setup path."""
    with (
        patch.object(hass, "async_create_task"),
        patch(
            "homeassistant.components.izone.discovery.pizone.discovery",
            return_value=Mock(start_discovery=AsyncMock(), close=AsyncMock()),
        ),
    ):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_EXCLUDE: list(uids)}}
        )


async def async_install_discovery_service(
    hass: HomeAssistant, *controllers: Mock
) -> Mock:
    """Start the discovery service with mocked pizone and optional controllers."""
    mock_pi_disco = create_mock_discovery_service(*controllers).pi_disco
    mock_pi_disco.start_discovery = AsyncMock()
    mock_pi_disco.close = AsyncMock()
    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.discovery",
            return_value=mock_pi_disco,
        ),
    ):
        service = await izone_discovery.async_start_discovery_service(hass)
    assert DATA_DISCOVERY_SERVICE in hass.data
    return service


@pytest.fixture
def mock_entry_setup() -> Generator[None]:
    """Patch climate platform setup for entry-creating config flow tests."""
    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ):
        yield


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
        mock_disco.return_value.close = AsyncMock()
        mock_disco.return_value.fetch_controller = AsyncMock(
            return_value=mock_controller
        )
        mock_disco.return_value.fetch_controllers = AsyncMock(
            return_value={mock_controller.device_uid: mock_controller}
        )
        yield mock_disco


@pytest.fixture
async def mock_zones() -> list[AsyncMock]:
    """Create a list of mock zones."""
    return [create_mock_zone(index=0, name="Living Room")]


@pytest.fixture
async def mock_controller(mock_zones: list[AsyncMock]) -> AsyncMock:
    """Create a mock controller."""
    return create_mock_controller(
        device_uid="000000001",
        device_ip="192.0.2.1",
        ras_mode="master",
        zone_ctrl=1,
        zones_total=1,
    )
