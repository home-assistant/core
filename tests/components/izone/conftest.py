"""Fixtures for iZone integration tests."""

from collections.abc import AsyncGenerator, Coroutine, Generator, Iterable
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from pizone import Controller, ControllerEndpoint, Zone
import pytest

from homeassistant.components.izone.const import DOMAIN
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for iZone with a stored host."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="iZone 000000001",
        data={CONF_HOST: "192.0.2.1"},
        entry_id="test_entry_id",
        unique_id="000000001",
        version=2,
    )


def create_mock_controller(
    device_uid: str = "000000001",
    device_ip: str = "192.0.2.1",
    sys_type: str = "iZone310",
    zones_total: int = 4,
    zone_ctrl: int = 1,
    ras_mode: str = "master",
    free_air_enabled: bool = False,
    free_air: bool = False,
    is_on: bool = True,
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
    controller.free_air = free_air
    controller.is_on = is_on
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
    controller.zones = []
    controller.refresh_all = AsyncMock()
    controller.close = AsyncMock()
    controller.set_temp_setpoint = AsyncMock()
    controller.set_fan = AsyncMock()
    controller.set_on = AsyncMock()
    controller.set_mode = AsyncMock()
    controller.set_free_air = AsyncMock()
    return controller


def create_mock_endpoint(
    uid: str = "000000001",
    host: str = "192.0.2.1",
) -> ControllerEndpoint:
    """Create a ControllerEndpoint for config-flow discovery patches."""
    return ControllerEndpoint(uid=uid, host=host)


def endpoint_from_controller(controller: Mock) -> ControllerEndpoint:
    """Map a mock controller's uid/ip into a ControllerEndpoint."""
    return ControllerEndpoint(uid=controller.device_uid, host=controller.device_ip)


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
    zone.set_airflow_min = AsyncMock()
    zone.set_airflow_max = AsyncMock()
    zone.set_temp_setpoint = AsyncMock()
    zone.set_mode = AsyncMock()
    return zone


@contextmanager
def patch_discovered_controllers(
    controllers: Mock | dict[str, Mock] | Iterable[Mock],
) -> Generator[tuple[AsyncMock, AsyncMock]]:
    """Patch discovery helpers using mock controllers' uid/ip."""
    if isinstance(controllers, dict):
        ctrl_list = list(controllers.values())
    elif isinstance(controllers, Mock):
        ctrl_list = [controllers]
    else:
        ctrl_list = list(controllers)
    endpoints = {
        controller.device_uid: endpoint_from_controller(controller)
        for controller in ctrl_list
    }

    async def _discover_all(
        hass: HomeAssistant,
    ) -> dict[str, ControllerEndpoint]:
        return dict(endpoints)

    async def _discover_one(hass: HomeAssistant, uid: str) -> ControllerEndpoint | None:
        return endpoints.get(uid)

    mock_discover_all = AsyncMock(side_effect=_discover_all)
    mock_discover_one = AsyncMock(side_effect=_discover_one)
    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_all_endpoints",
            new=mock_discover_all,
        ),
        patch(
            "homeassistant.components.izone.discovery.async_discover_endpoint",
            new=mock_discover_one,
        ),
    ):
        yield mock_discover_all, mock_discover_one


async def async_load_yaml_exclude(hass: HomeAssistant, *uids: str) -> None:
    """Load deprecated YAML exclude config through the integration setup path."""

    def _discard_task(
        coro: Coroutine[Any, Any, Any], *_args: object, **_kwargs: object
    ) -> Mock:
        # Import flow is scheduled by async_setup; tests only need DATA_CONFIG.
        coro.close()
        return Mock()

    with patch.object(hass, "async_create_task", side_effect=_discard_task):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_EXCLUDE: list(uids)}}
        )


@pytest.fixture
def mock_entry_setup() -> Generator[None]:
    """Skip full entry setup for config-flow create-entry tests."""
    with patch(
        "homeassistant.components.izone.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_zones() -> list[Mock]:
    """Create a list of mock zones."""
    return [create_mock_zone(index=0, name="Living Room")]


@pytest.fixture
def mock_controller(mock_zones: list[Mock]) -> Mock:
    """Create a mock controller with zones attached."""
    controller = create_mock_controller(
        device_uid="000000001",
        device_ip="192.0.2.1",
        ras_mode="master",
        zone_ctrl=1,
        zones_total=1,
    )
    controller.zones = mock_zones
    return controller


@pytest.fixture
def mock_discovery_service(mock_controller: Mock) -> Mock:
    """Return a mock pizone DiscoveryService wired for entry setup."""
    service = Mock()
    service.scan = AsyncMock()
    service.close = AsyncMock()
    service.discover_all = AsyncMock(
        return_value=[endpoint_from_controller(mock_controller)]
    )
    service.discover_by_uid = AsyncMock(
        return_value=endpoint_from_controller(mock_controller)
    )
    service.create_controller = AsyncMock(return_value=mock_controller)
    return service


@pytest.fixture
def mock_create_discovery(
    mock_discovery_service: Mock,
) -> Generator[AsyncMock]:
    """Patch pizone.create_discovery to return the mock discovery service."""
    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.create_discovery",
            new=AsyncMock(return_value=mock_discovery_service),
        ) as mock_create,
    ):
        yield mock_create


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms to load in integration tests."""
    return [Platform.CLIMATE]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_discovery: AsyncMock,
    platforms: list[Platform],
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the iZone integration with a mocked discovery/controller stack."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.izone.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry
