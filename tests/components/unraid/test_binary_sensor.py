"""Tests for Unraid binary sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.unraid import UnraidRuntimeData
from homeassistant.components.unraid.binary_sensor import (
    ArrayStartedBinarySensor,
    DiskHealthBinarySensor,
    ParityCheckRunningBinarySensor,
    ParityStatusBinarySensor,
    ParityValidBinarySensor,
    UPSConnectedBinarySensor,
    async_setup_entry,
)
from homeassistant.components.unraid.coordinator import UnraidStorageData
from homeassistant.components.unraid.models import (
    ArrayDisk,
    ParityCheck,
    UPSBattery,
    UPSDevice,
)


@pytest.fixture
def mock_storage_coordinator():
    """Create a mock storage coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    return coordinator


@pytest.fixture
def mock_system_coordinator():
    """Create a mock system coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    return coordinator


@pytest.fixture
def mock_disk():
    """Create a mock disk."""
    return ArrayDisk(
        id="disk:1",
        idx=1,
        device="sda",
        name="Disk 1",
        type="DATA",
        status="DISK_OK",
        temp=35,
        is_spinning=True,
        smart_status="PASSED",
        fs_type="XFS",
    )


@pytest.fixture
def mock_ups():
    """Create a mock UPS device."""
    return UPSDevice(
        id="ups:1",
        name="APC Smart-UPS",
        status="Online",
        battery=UPSBattery(charge_level=95, estimated_runtime=1200),
    )


class TestDiskHealthBinarySensor:
    """Tests for DiskHealthBinarySensor."""

    def test_init(self, mock_storage_coordinator, mock_disk):
        """Test sensor initialization."""
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        assert sensor._attr_unique_id == "test-uuid_disk_health_disk:1"
        assert sensor._attr_name == "Disk Disk 1 Health"
        assert sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM

    def test_is_on_disk_ok(self, mock_storage_coordinator, mock_disk):
        """Test is_on returns False when disk is healthy."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[mock_disk],
            parities=[],
            caches=[],
        )
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        assert sensor.is_on is False  # No problem

    def test_is_on_disk_error(self, mock_storage_coordinator, mock_disk):
        """Test is_on returns True when disk has problem."""
        mock_disk.status = "DISK_DISABLED"
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[mock_disk],
            parities=[],
            caches=[],
        )
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        assert sensor.is_on is True  # Problem detected

    def test_is_on_no_data(self, mock_storage_coordinator, mock_disk):
        """Test is_on returns None when no data."""
        mock_storage_coordinator.data = None
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        assert sensor.is_on is None

    def test_is_on_disk_not_found(self, mock_storage_coordinator, mock_disk):
        """Test is_on returns None when disk not found in data."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],  # Empty disks list
            parities=[],
            caches=[],
        )
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        assert sensor.is_on is None

    def test_is_on_status_none(self, mock_storage_coordinator, mock_disk):
        """Test is_on returns None when disk status is None."""
        mock_disk.status = None
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[mock_disk],
            parities=[],
            caches=[],
        )
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        assert sensor.is_on is None

    def test_extra_state_attributes(self, mock_storage_coordinator, mock_disk):
        """Test extra state attributes."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[mock_disk],
            parities=[],
            caches=[],
        )
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        attrs = sensor.extra_state_attributes
        assert attrs["status"] == "DISK_OK"
        assert attrs["device"] == "sda"
        assert attrs["filesystem"] == "XFS"
        assert attrs["temperature"] == 35
        assert attrs["smart_status"] == "PASSED"
        assert attrs["standby"] is False
        assert attrs["spinning"] is True

    def test_extra_state_attributes_no_data(self, mock_storage_coordinator, mock_disk):
        """Test extra_state_attributes returns empty dict when no data."""
        mock_storage_coordinator.data = None
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=mock_disk,
        )
        assert sensor.extra_state_attributes == {}

    def test_get_disk_from_parities(self, mock_storage_coordinator):
        """Test _get_disk finds disk in parities list."""
        parity_disk = ArrayDisk(id="parity:1", name="Parity", status="DISK_OK")
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[parity_disk],
            caches=[],
        )
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=parity_disk,
        )
        assert sensor.is_on is False

    def test_get_disk_from_caches(self, mock_storage_coordinator):
        """Test _get_disk finds disk in caches list."""
        cache_disk = ArrayDisk(id="cache:1", name="Cache", status="DISK_OK")
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[cache_disk],
        )
        sensor = DiskHealthBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            disk=cache_disk,
        )
        assert sensor.is_on is False


class TestParityStatusBinarySensor:
    """Tests for ParityStatusBinarySensor."""

    def test_init(self, mock_storage_coordinator):
        """Test sensor initialization."""
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor._attr_unique_id == "test-uuid_parity_status"
        assert sensor._attr_name == "Parity Status"
        assert sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM

    def test_is_on_running(self, mock_storage_coordinator):
        """Test is_on returns True when parity check running."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="RUNNING", progress=50, errors=0),
        )
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is True

    def test_is_on_paused(self, mock_storage_coordinator):
        """Test is_on returns True when parity check paused."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="PAUSED", progress=50, errors=0),
        )
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is True

    def test_is_on_completed(self, mock_storage_coordinator):
        """Test is_on returns False when parity check completed."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="COMPLETED", progress=100, errors=0),
        )
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is False

    def test_is_on_no_data(self, mock_storage_coordinator):
        """Test is_on returns None when no data."""
        mock_storage_coordinator.data = None
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_is_on_no_parity_status(self, mock_storage_coordinator):
        """Test is_on returns None when no parity status."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=None,
        )
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_is_on_status_none(self, mock_storage_coordinator):
        """Test is_on returns None when status is None."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status=None),
        )
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_extra_state_attributes(self, mock_storage_coordinator):
        """Test extra state attributes."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="COMPLETED", progress=100, errors=0),
        )
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        attrs = sensor.extra_state_attributes
        assert attrs["status"] == "completed"
        assert attrs["progress"] == 100
        assert attrs["errors"] == 0

    def test_extra_state_attributes_no_data(self, mock_storage_coordinator):
        """Test extra_state_attributes returns empty dict when no data."""
        mock_storage_coordinator.data = None
        sensor = ParityStatusBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.extra_state_attributes == {}


class TestArrayStartedBinarySensor:
    """Tests for ArrayStartedBinarySensor."""

    def test_init(self, mock_storage_coordinator):
        """Test sensor initialization."""
        sensor = ArrayStartedBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor._attr_unique_id == "test-uuid_array_started"
        assert sensor._attr_name == "Array Started"
        assert sensor._attr_device_class == BinarySensorDeviceClass.RUNNING

    def test_is_on_started(self, mock_storage_coordinator):
        """Test is_on returns True when array started."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
        )
        sensor = ArrayStartedBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is True

    def test_is_on_stopped(self, mock_storage_coordinator):
        """Test is_on returns False when array stopped."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STOPPED",
            disks=[],
            parities=[],
            caches=[],
        )
        sensor = ArrayStartedBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is False

    def test_is_on_no_data(self, mock_storage_coordinator):
        """Test is_on returns None when no data."""
        mock_storage_coordinator.data = None
        sensor = ArrayStartedBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_is_on_array_state_none(self, mock_storage_coordinator):
        """Test is_on returns None when array_state is None."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state=None,
            disks=[],
            parities=[],
            caches=[],
        )
        sensor = ArrayStartedBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None


class TestParityCheckRunningBinarySensor:
    """Tests for ParityCheckRunningBinarySensor."""

    def test_init(self, mock_storage_coordinator):
        """Test sensor initialization."""
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor._attr_unique_id == "test-uuid_parity_check_running"
        assert sensor._attr_name == "Parity Check Running"
        assert sensor._attr_device_class == BinarySensorDeviceClass.RUNNING

    def test_is_on_running(self, mock_storage_coordinator):
        """Test is_on returns True when parity check running."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="RUNNING", progress=50),
        )
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is True

    def test_is_on_paused(self, mock_storage_coordinator):
        """Test is_on returns True when parity check paused."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="PAUSED", progress=50),
        )
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is True

    def test_is_on_completed(self, mock_storage_coordinator):
        """Test is_on returns False when parity check completed."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="COMPLETED", progress=100),
        )
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is False

    def test_is_on_no_data(self, mock_storage_coordinator):
        """Test is_on returns None when no data."""
        mock_storage_coordinator.data = None
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_is_on_no_parity_status(self, mock_storage_coordinator):
        """Test is_on returns None when no parity status."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=None,
        )
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_is_on_status_none(self, mock_storage_coordinator):
        """Test is_on returns None when status is None."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status=None),
        )
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_extra_state_attributes(self, mock_storage_coordinator):
        """Test extra state attributes."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="RUNNING", progress=50),
        )
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        attrs = sensor.extra_state_attributes
        assert attrs["status"] == "running"
        assert attrs["progress"] == 50

    def test_extra_state_attributes_no_data(self, mock_storage_coordinator):
        """Test extra_state_attributes returns empty dict when no data."""
        mock_storage_coordinator.data = None
        sensor = ParityCheckRunningBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.extra_state_attributes == {}


class TestParityValidBinarySensor:
    """Tests for ParityValidBinarySensor."""

    def test_init(self, mock_storage_coordinator):
        """Test sensor initialization."""
        sensor = ParityValidBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor._attr_unique_id == "test-uuid_parity_valid"
        assert sensor._attr_name == "Parity Valid"
        assert sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM

    def test_is_on_failed(self, mock_storage_coordinator):
        """Test is_on returns True when parity failed."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="FAILED", errors=0),
        )
        sensor = ParityValidBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is True  # Problem detected

    def test_is_on_with_errors(self, mock_storage_coordinator):
        """Test is_on returns True when parity has errors."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="COMPLETED", errors=5),
        )
        sensor = ParityValidBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is True  # Problem detected

    def test_is_on_valid(self, mock_storage_coordinator):
        """Test is_on returns False when parity is valid."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="COMPLETED", errors=0),
        )
        sensor = ParityValidBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is False  # No problem

    def test_is_on_no_data(self, mock_storage_coordinator):
        """Test is_on returns None when no data."""
        mock_storage_coordinator.data = None
        sensor = ParityValidBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.is_on is None

    def test_extra_state_attributes(self, mock_storage_coordinator):
        """Test extra state attributes."""
        mock_storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[],
            parities=[],
            caches=[],
            parity_status=ParityCheck(status="COMPLETED", errors=0),
        )
        sensor = ParityValidBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        attrs = sensor.extra_state_attributes
        assert attrs["status"] == "completed"
        assert attrs["errors"] == 0

    def test_extra_state_attributes_no_data(self, mock_storage_coordinator):
        """Test extra_state_attributes returns empty dict when no data."""
        mock_storage_coordinator.data = None
        sensor = ParityValidBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.extra_state_attributes == {}


class TestUPSConnectedBinarySensor:
    """Tests for UPSConnectedBinarySensor."""

    def test_init(self, mock_system_coordinator, mock_ups):
        """Test sensor initialization."""
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        assert sensor._attr_unique_id == "test-uuid_ups_ups:1_connected"
        assert sensor._attr_name == "UPS Connected"
        assert sensor._attr_device_class == BinarySensorDeviceClass.CONNECTIVITY

    def test_is_on_online(self, mock_system_coordinator, mock_ups):
        """Test is_on returns True when UPS online."""
        mock_system_coordinator.data = MagicMock()
        mock_system_coordinator.data.ups_devices = [mock_ups]
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        assert sensor.is_on is True

    def test_is_on_offline(self, mock_system_coordinator, mock_ups):
        """Test is_on returns False when UPS offline."""
        mock_ups.status = "Offline"
        mock_system_coordinator.data = MagicMock()
        mock_system_coordinator.data.ups_devices = [mock_ups]
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        assert sensor.is_on is False

    def test_is_on_status_none(self, mock_system_coordinator, mock_ups):
        """Test is_on returns False when UPS status is None."""
        mock_ups.status = None
        mock_system_coordinator.data = MagicMock()
        mock_system_coordinator.data.ups_devices = [mock_ups]
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        assert sensor.is_on is False

    def test_is_on_ups_not_found(self, mock_system_coordinator, mock_ups):
        """Test is_on returns False when UPS not found."""
        mock_system_coordinator.data = MagicMock()
        mock_system_coordinator.data.ups_devices = []
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        assert sensor.is_on is False

    def test_is_on_no_data(self, mock_system_coordinator, mock_ups):
        """Test is_on returns False when no data."""
        mock_system_coordinator.data = None
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        assert sensor.is_on is False

    def test_extra_state_attributes(self, mock_system_coordinator, mock_ups):
        """Test extra state attributes."""
        mock_system_coordinator.data = MagicMock()
        mock_system_coordinator.data.ups_devices = [mock_ups]
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        attrs = sensor.extra_state_attributes
        assert attrs["model"] == "APC Smart-UPS"
        assert attrs["status"] == "Online"
        assert attrs["battery_level"] == 95

    def test_extra_state_attributes_no_data(self, mock_system_coordinator, mock_ups):
        """Test extra_state_attributes returns empty dict when no UPS."""
        mock_system_coordinator.data = None
        sensor = UPSConnectedBinarySensor(
            coordinator=mock_system_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
            ups=mock_ups,
        )
        assert sensor.extra_state_attributes == {}


class TestBinarySensorAvailability:
    """Test availability property for binary sensors."""

    def test_available_true(self, mock_storage_coordinator):
        """Test sensor is available when coordinator succeeds."""
        mock_storage_coordinator.last_update_success = True
        sensor = ArrayStartedBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.available is True

    def test_available_false(self, mock_storage_coordinator):
        """Test sensor is not available when coordinator fails."""
        mock_storage_coordinator.last_update_success = False
        sensor = ArrayStartedBinarySensor(
            coordinator=mock_storage_coordinator,
            server_uuid="test-uuid",
            server_name="tower",
        )
        assert sensor.available is False


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_entities(self, hass):
        """Test async_setup_entry creates expected entities."""
        mock_disk = ArrayDisk(id="disk:1", name="Disk 1", status="DISK_OK")
        mock_ups = UPSDevice(id="ups:1", name="APC", status="Online")

        # Setup mock coordinators
        storage_coordinator = MagicMock()
        storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[mock_disk],
            parities=[],
            caches=[],
        )

        system_coordinator = MagicMock()
        system_data = MagicMock()
        system_data.ups_devices = [mock_ups]
        system_coordinator.data = system_data

        # Create mock config entry
        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
                "manufacturer": "Supermicro",
                "model": "X11",
            },
        )

        # Track added entities
        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Verify expected entities were created
        assert len(added_entities) > 0

        # Check for expected sensor types
        entity_types = [type(e).__name__ for e in added_entities]
        assert "ArrayStartedBinarySensor" in entity_types
        assert "ParityCheckRunningBinarySensor" in entity_types
        assert "ParityValidBinarySensor" in entity_types
        assert "ParityStatusBinarySensor" in entity_types
        assert "DiskHealthBinarySensor" in entity_types
        assert "UPSConnectedBinarySensor" in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_no_ups(self, hass):
        """Test async_setup_entry works without UPS."""
        mock_disk = ArrayDisk(id="disk:1", name="Disk 1", status="DISK_OK")

        storage_coordinator = MagicMock()
        storage_coordinator.data = UnraidStorageData(
            array_state="STARTED",
            disks=[mock_disk],
            parities=[],
            caches=[],
        )

        system_coordinator = MagicMock()
        system_coordinator.data = None  # No system data

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
            },
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Verify no UPS sensors created
        entity_types = [type(e).__name__ for e in added_entities]
        assert "UPSConnectedBinarySensor" not in entity_types

    @pytest.mark.asyncio
    async def test_setup_entry_no_storage_data(self, hass):
        """Test async_setup_entry works without storage data."""
        storage_coordinator = MagicMock()
        storage_coordinator.data = None

        system_coordinator = MagicMock()
        system_coordinator.data = None

        mock_entry = MagicMock()
        mock_entry.data = {"host": "192.168.1.100"}
        mock_entry.runtime_data = UnraidRuntimeData(
            api_client=MagicMock(),
            system_coordinator=system_coordinator,
            storage_coordinator=storage_coordinator,
            server_info={
                "uuid": "test-uuid",
                "name": "tower",
            },
        )

        added_entities = []

        def mock_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Still creates array sensors (just no disk sensors)
        assert (
            len(added_entities) >= 4
        )  # ArrayStarted, ParityCheck, ParityValid, ParityStatus
