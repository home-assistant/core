"""Configure py.test."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from total_connect_client import ArmingState, TotalConnectClient
from total_connect_client.device import TotalConnectDevice
from total_connect_client.location import TotalConnectLocation
from total_connect_client.partition import TotalConnectPartition

from homeassistant.components.totalconnect.const import (
    AUTO_BYPASS,
    CODE_REQUIRED,
    CONF_USERCODES,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .common import LOCATION_ID
from .const import PASSWORD, USERCODES, USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_partition() -> TotalConnectPartition:
    """Create a mock TotalConnectPartition."""
    partition = AsyncMock(spec=TotalConnectPartition, autospec=True)
    partition.partitionid = 1
    partition.name = "Test1"
    partition.is_stay_armed = False
    partition.is_fire_armed = False
    partition.is_common_armed = False
    partition.is_locked = False
    partition.is_new_partition = False
    partition.is_night_stay_enabled = 0
    partition.exit_delay_timer = 0
    partition.arming_state = ArmingState.DISARMED
    return partition


@pytest.fixture
def mock_partition_2() -> TotalConnectPartition:
    """Create a mock TotalConnectPartition."""
    partition = AsyncMock(spec=TotalConnectPartition, autospec=True)
    partition.partitionid = 2
    partition.name = "Test2"
    partition.is_stay_armed = False
    partition.is_fire_armed = False
    partition.is_common_armed = False
    partition.is_locked = False
    partition.is_new_partition = False
    partition.is_night_stay_enabled = 0
    partition.exit_delay_timer = 0
    partition.arming_state = ArmingState.DISARMED
    return partition


@pytest.fixture
def mock_location(
    mock_partition: AsyncMock, mock_partition_2: AsyncMock
) -> TotalConnectLocation:
    """Create a mock TotalConnectLocation."""
    location = AsyncMock(spec=TotalConnectLocation, autospec=True)
    location.location_id = LOCATION_ID
    location.security_device_id = 7654321
    location.set_usercode.return_value = True
    location.partitions = {1: mock_partition, 2: mock_partition_2}
    location.devices = {
        7654321: TotalConnectDevice(load_json_object_fixture("device_1.json", DOMAIN))
    }
    return location


@pytest.fixture
def mock_client(mock_location: TotalConnectLocation) -> Generator[TotalConnectClient]:
    """Mock a TotalConnectClient for testing."""
    with (
        patch(
            "homeassistant.components.totalconnect.config_flow.TotalConnectClient",
            autospec=True,
        ) as client,
        patch("homeassistant.components.totalconnect.TotalConnectClient", new=client),
    ):
        client.return_value.get_number_locations.return_value = 1
        client.return_value.locations = {mock_location.location_id: mock_location}
        yield client.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_USERCODES: USERCODES,
        },
        options={AUTO_BYPASS: False, CODE_REQUIRED: False},
    )
