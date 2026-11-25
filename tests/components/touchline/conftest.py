"""Fixtures for the Touchline tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytouchline_extended import (
    ControllerOperationMode,
    ControllerStatus,
    DiscoveredController,
    RoomOperationMode,
    RoomStatus,
    TemperatureUnit,
    TouchlineErrorCode,
    TouchlineState,
    WeekProgram,
)

from homeassistant.components.touchline.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

TEST_HOST = "1.2.3.4"
TEST_UNIQUE_ID = "1"

CONTROLLER_STATUS = ControllerStatus(
    unique_id="51FF6E064965525706340287",
    controller_id=1,
    paired_devices=1,
    total_devices=1,
    is_master=True,
    slave_controllers=0,
    hostname="ROTH-01",
    mac_address="00:11:22:33:44:55",
    ip_address=TEST_HOST,
    stm_app_version="A.FA",
    stm_bootloader_version="1.0",
    actuator_app_version="1.0",
    actuator_bootloader_version="1.0",
    operation_mode=ControllerOperationMode.DAY,
    error_code=TouchlineErrorCode.NO_ERROR,
    safety_tripped=False,
    dew_point_active=False,
    week_program_warning=False,
    system_status=0,
    timestamp=0,
)

ROOM_STATUS = RoomStatus(
    index=0,
    device_id=0,
    controller_id=1,
    unique_id="1-0",
    name="Zone 1",
    temperature=21.5,
    target_temperature=22.0,
    min_temperature=5.0,
    max_temperature=30.0,
    temperature_step=0.5,
    operation_mode=RoomOperationMode.NORMAL,
    operation_mode_enabled=True,
    week_program=WeekProgram.OFF,
    week_program_enabled=True,
    temperature_unit=TemperatureUnit.CELSIUS,
)


DISCOVERED_CONTROLLER = DiscoveredController(
    controller_id=1,
    unique_id="51FF6E064965525706340287",
    url=f"http://{TEST_HOST}",
    ip_address=TEST_HOST,
    mac_address="5C-C2-13-00-81-49",
    name="ID10655-47951974",
    protocol_version="R100",
)


def make_state(*rooms: RoomStatus) -> TouchlineState:
    """Return a controller state with the given thermostats."""
    return TouchlineState(controller=CONTROLLER_STATUS, rooms=rooms)


@pytest.fixture
def mock_touchline_controller() -> Generator[MagicMock]:
    """Mock TouchlineController across all integration modules."""
    with (
        patch(
            "homeassistant.components.touchline.coordinator.TouchlineController",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.touchline.config_flow.TouchlineController",
            new=mock_class,
        ),
    ):
        instance = mock_class.return_value
        instance.url = TEST_HOST
        instance.fetch_async.return_value = make_state(ROOM_STATUS)
        instance.set_room_target_temperature_async.return_value = True
        instance.set_room_operation_mode_async.return_value = True
        instance.set_room_week_program_async.return_value = True
        yield instance


@pytest.fixture
def mock_discover_controllers() -> Generator[AsyncMock]:
    """Mock searching two networks, which find no controllers by default."""
    with (
        patch(
            "homeassistant.components.network.async_get_ipv4_broadcast_addresses",
            return_value={"10.255.255.255", "192.168.1.255"},
        ),
        patch(
            "homeassistant.components.touchline.config_flow.discover_controllers",
            return_value=[],
        ) as mock_discover,
    ):
        yield mock_discover


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.touchline.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_HOST,
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
        unique_id=TEST_UNIQUE_ID,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchline_controller: MagicMock,
) -> MockConfigEntry:
    """Set up the Touchline integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
