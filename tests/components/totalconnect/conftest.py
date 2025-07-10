"""Configure py.test."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from total_connect_client import ArmingState, TotalConnectClient
from total_connect_client.device import TotalConnectDevice
from total_connect_client.location import TotalConnectLocation
from total_connect_client.partition import TotalConnectPartition
from total_connect_client.zone import TotalConnectZone, ZoneStatus, ZoneType

from homeassistant.components.totalconnect.const import (
    AUTO_BYPASS,
    CODE_REQUIRED,
    CONF_USERCODES,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CODE, LOCATION_ID, PASSWORD, USERCODES, USERNAME

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


def create_mock_zone(
    identifier: int,
    partition: str,
    description: str,
    status: ZoneStatus,
    zone_type_id: int,
    can_be_bypassed: bool,
    battery_level: int,
    signal_strength: int,
    sensor_serial_number: str | None,
    loop_number: int | None,
    response_type: str | None,
    alarm_report_state: str | None,
    supervision_type: str | None,
    chime_state: str | None,
    device_type: str | None,
) -> AsyncMock:
    """Create a mock TotalConnectZone."""
    zone = AsyncMock(spec=TotalConnectZone, autospec=True)
    zone.zoneid = identifier
    zone.partition = partition
    zone.description = description
    zone.status = status
    zone.zone_type_id = zone_type_id
    zone.can_be_bypassed = can_be_bypassed
    zone.battery_level = battery_level
    zone.signal_strength = signal_strength
    zone.sensor_serial_number = sensor_serial_number
    zone.loop_number = loop_number
    zone.response_type = response_type
    zone.alarm_report_state = alarm_report_state
    zone.supervision_type = supervision_type
    zone.chime_state = chime_state
    zone.device_type = device_type
    zone.is_type_security.return_value = zone_type_id in (
        ZoneType.SECURITY,
        ZoneType.ENTRY_EXIT1,
        ZoneType.ENTRY_EXIT2,
        ZoneType.PERIMETER,
        ZoneType.INTERIOR_FOLLOWER,
        ZoneType.TROUBLE_ALARM,
        ZoneType.SILENT_24HR,
        ZoneType.AUDIBLE_24HR,
        ZoneType.INTERIOR_DELAY,
        ZoneType.LYRIC_LOCAL_ALARM,
        ZoneType.PROA7_GARAGE_MONITOR,
    )
    zone.is_type_button.return_value = (
        zone.is_type_security.return_value and not can_be_bypassed
    ) or zone_type_id in (
        ZoneType.PROA7_MEDICAL,
        ZoneType.AUDIBLE_24HR,
        ZoneType.SILENT_24HR,
        ZoneType.RF_ARM_STAY,
        ZoneType.RF_ARM_AWAY,
        ZoneType.RF_DISARM,
    )
    return zone


def create_mock_zone_from_dict(
    zone_data: dict[str, Any],
) -> AsyncMock:
    """Create a mock TotalConnectZone from a dictionary."""
    return create_mock_zone(
        zone_data["ZoneID"],
        zone_data["PartitionId"],
        zone_data["ZoneDescription"],
        ZoneStatus(zone_data["ZoneStatus"]),
        zone_data["ZoneTypeId"],
        zone_data["CanBeBypassed"],
        zone_data.get("Batterylevel"),
        zone_data.get("Signalstrength"),
        (zone_data["zoneAdditionalInfo"] or {}).get("SensorSerialNumber"),
        (zone_data["zoneAdditionalInfo"] or {}).get("LoopNumber"),
        (zone_data["zoneAdditionalInfo"] or {}).get("ResponseType"),
        (zone_data["zoneAdditionalInfo"] or {}).get("AlarmReportState"),
        (zone_data["zoneAdditionalInfo"] or {}).get("ZoneSupervisionType"),
        (zone_data["zoneAdditionalInfo"] or {}).get("ChimeState"),
        (zone_data["zoneAdditionalInfo"] or {}).get("DeviceType"),
    )


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
    location.zones = {
        z["ZoneID"]: create_mock_zone_from_dict(z)
        for z in load_json_array_fixture("zones.json", DOMAIN)
    }
    location.is_low_battery.return_value = False
    location.is_cover_tampered.return_value = False
    location.is_ac_loss.return_value = False
    location.arming_state = ArmingState.DISARMED
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
        client.return_value.usercodes = {mock_location.location_id: CODE}
        yield client.return_value


@pytest.fixture
def code_required() -> bool:
    """Return whether a code is required."""
    return False


@pytest.fixture
def mock_config_entry(code_required: bool) -> MockConfigEntry:
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_USERCODES: USERCODES,
        },
        options={AUTO_BYPASS: False, CODE_REQUIRED: code_required},
    )
