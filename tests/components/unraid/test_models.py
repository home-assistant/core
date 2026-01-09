"""Model tests for the Unraid integration."""

from datetime import UTC, datetime

import pytest

from homeassistant.components.unraid import models

from .conftest import load_json


def test_base_model_ignores_unknown_fields() -> None:
    """Test that unknown fields are ignored by the base model."""

    class SampleModel(models.UnraidBaseModel):
        required: str

    data = {"required": "ok", "unexpected": "ignored"}
    parsed = SampleModel.model_validate(data)
    assert parsed.required == "ok"
    assert not hasattr(parsed, "unexpected")


def test_system_info_parses_core_sections() -> None:
    """Test parsing of core sections in SystemInfo model."""
    payload = load_json("system_info.json")
    info = models.SystemInfo.model_validate(payload)

    assert info.time.isoformat() == "2025-12-23T10:30:00+00:00"
    assert info.system.uuid == "abc-123"
    assert info.cpu.brand == "AMD Ryzen"
    assert info.cpu.threads == 16
    assert info.cpu.cores == 8
    assert info.cpu.packages.temp == [45.2]
    assert info.cpu.packages.total_power == 65.5
    assert info.os.hostname == "tower"
    assert info.versions.core.unraid == "7.2.0"
    assert info.versions.core.api == "4.29.2"


def test_metrics_parses_cpu_and_memory() -> None:
    """Test parsing of CPU and memory metrics."""
    payload = load_json("metrics.json")
    metrics = models.Metrics.model_validate(payload)

    assert metrics.cpu.percent_total == pytest.approx(23.5)
    assert metrics.memory.total == 17179869184
    assert metrics.memory.used == 8589934592
    assert metrics.memory.free == 8589934592
    assert metrics.memory.percent_total == pytest.approx(50.0)
    assert metrics.memory.percent_swap_total == pytest.approx(0.0)


def test_array_parses_capacity_and_disks() -> None:
    """Test parsing of array capacity and disks."""
    payload = load_json("array.json")
    array = models.UnraidArray.model_validate(payload)

    assert array.state == "STARTED"
    assert array.capacity.total_bytes == 1000 * 1024
    assert array.capacity.used_bytes == 400 * 1024
    assert array.capacity.free_bytes == 600 * 1024
    assert array.capacity.usage_percent == pytest.approx(40.0)

    disk = array.disks[0]
    assert disk.id == "disk:1"
    assert disk.idx == 1
    assert disk.device == "sda"
    assert disk.name == "Disk 1"
    assert disk.type == "DATA"
    assert disk.size_bytes == 500000 * 1024  # size field is in KB
    assert disk.fs_size_bytes == 400000 * 1024  # fsSize field is in KB
    assert disk.fs_used_bytes == 200000 * 1024  # fsUsed field is in KB
    assert disk.fs_free_bytes == 200000 * 1024  # fsFree field is in KB
    assert disk.usage_percent == pytest.approx(50.0)
    assert disk.temp == 35
    assert disk.status == "DISK_OK"

    assert array.parity_check_status.status == "COMPLETED"
    assert array.parity_check_status.progress == 100
    assert array.parity_check_status.errors == 0


def test_docker_container_parses_ports_and_state() -> None:
    """Test parsing of Docker container ports and state."""
    payload = load_json("docker.json")
    container = models.DockerContainer.model_validate(payload)

    assert container.id == "ct:1"
    assert container.name == "web"
    assert container.state == "RUNNING"
    assert container.image == "nginx:latest"
    assert container.web_ui_url == "https://tower/apps/web"
    assert container.icon_url == "https://cdn/icons/web.png"
    assert container.ports[0].private_port == 80
    assert container.ports[0].public_port == 8080
    assert container.ports[0].type == "tcp"


def test_vm_domain_parses_state_and_ids() -> None:
    """Test parsing of VM domain state and IDs."""
    payload = load_json("vms.json")
    domain = models.VmDomain.model_validate(payload)

    assert domain.id == "vm:1"
    assert domain.name == "Ubuntu"
    assert domain.state == "RUNNING"
    assert domain.memory == 2147483648
    assert domain.vcpu == 4


def test_ups_device_parses_battery_and_power() -> None:
    """Test parsing of UPS device battery and power."""
    payload = load_json("ups.json")
    ups = models.UPSDevice.model_validate(payload)

    assert ups.id == "ups:1"
    assert ups.name == "APC"
    assert ups.status == "Online"
    assert ups.battery.charge_level == 95
    assert ups.battery.estimated_runtime == 1200
    assert ups.power.input_voltage == pytest.approx(120.0)
    assert ups.power.output_voltage == pytest.approx(118.5)
    assert ups.power.load_percentage == pytest.approx(20.5)


def test_datetime_parsing_with_z_suffix() -> None:
    """Test that datetime with Z suffix is correctly parsed."""
    data = {"time": "2025-12-25T15:30:00Z"}
    info = models.SystemInfo.model_validate(data)
    assert info.time.isoformat() == "2025-12-25T15:30:00+00:00"


def test_datetime_parsing_with_offset() -> None:
    """Test that datetime with offset is correctly parsed."""
    data = {"time": "2025-12-25T15:30:00+05:00"}
    info = models.SystemInfo.model_validate(data)
    assert info.time.isoformat() == "2025-12-25T15:30:00+05:00"


def test_datetime_parsing_with_none() -> None:
    """Test that None datetime values are handled."""
    data = {"time": None}
    info = models.SystemInfo.model_validate(data)
    assert info.time is None


def test_datetime_parsing_already_datetime() -> None:
    """Test that datetime objects pass through unchanged."""

    dt = datetime(2025, 12, 25, 15, 30, 0, tzinfo=UTC)
    result = models._parse_datetime(dt)
    assert result == dt


def test_array_capacity_zero_total() -> None:
    """Test array capacity with zero total doesn't divide by zero."""
    capacity = models.ArrayCapacity(
        kilobytes=models.CapacityKilobytes(total=0, used=0, free=0)
    )
    assert capacity.usage_percent == 0.0


def test_disk_usage_percent_none_when_no_fs_size() -> None:
    """Test disk usage_percent returns None when fsSize is missing."""
    disk = models.ArrayDisk(id="disk:1", fs_size=None, fs_used=100)
    assert disk.usage_percent is None


def test_disk_usage_percent_none_when_fs_size_zero() -> None:
    """Test disk usage_percent returns None when fsSize is zero."""
    disk = models.ArrayDisk(id="disk:1", fs_size=0, fs_used=0)
    assert disk.usage_percent is None


def test_disk_size_bytes_none_when_missing() -> None:
    """Test disk size_bytes returns None when size is missing."""
    disk = models.ArrayDisk(id="disk:1", size=None)
    assert disk.size_bytes is None


def test_share_size_calculation() -> None:
    """Test share size calculation from used + free."""
    share = models.Share(id="share:1", name="appdata", size=0, used=500, free=500)
    # Size is 0 but calculated from used + free
    assert share.size_bytes == 1000 * 1024


def test_share_usage_percent_with_zero_size() -> None:
    """Test share usage_percent with zero calculated size."""
    share = models.Share(id="share:1", name="empty", size=0, used=0, free=0)
    assert share.usage_percent is None


def test_share_usage_percent_calculated() -> None:
    """Test share usage_percent is calculated correctly."""
    share = models.Share(id="share:1", name="data", size=1000, used=250, free=750)
    assert share.usage_percent == pytest.approx(25.0)


def test_share_used_bytes() -> None:
    """Test share used_bytes calculation."""
    share = models.Share(id="share:1", name="data", used=1000)
    assert share.used_bytes == 1000 * 1024


def test_share_free_bytes() -> None:
    """Test share free_bytes calculation."""
    share = models.Share(id="share:1", name="data", free=500)
    assert share.free_bytes == 500 * 1024


def test_model_defaults() -> None:
    """Test that models have proper defaults."""
    # SystemInfo with minimal data
    info = models.SystemInfo.model_validate({})
    assert info.time is None
    assert info.system.uuid is None
    assert info.cpu.brand is None
    assert info.cpu.packages.temp == []

    # Metrics with minimal data
    metrics = models.Metrics.model_validate({})
    assert metrics.cpu.percent_total is None
    assert metrics.memory.total is None


def test_ups_uptime_parsing() -> None:
    """Test InfoOs uptime field parsing."""
    data = {"uptime": "2025-12-01T00:00:00Z"}
    os_info = models.InfoOs.model_validate(data)
    assert os_info.uptime.isoformat() == "2025-12-01T00:00:00+00:00"


def test_disk_fs_properties() -> None:
    """Test all disk filesystem byte properties."""
    disk = models.ArrayDisk(
        id="disk:1",
        size=1000,
        fs_size=900,
        fs_used=450,
        fs_free=450,
    )
    assert disk.size_bytes == 1000 * 1024
    assert disk.fs_size_bytes == 900 * 1024
    assert disk.fs_used_bytes == 450 * 1024
    assert disk.fs_free_bytes == 450 * 1024
    assert disk.usage_percent == pytest.approx(50.0)


def test_container_port_defaults() -> None:
    """Test container port model with partial data."""
    port = models.ContainerPort.model_validate({"privatePort": 80})
    assert port.private_port == 80
    assert port.public_port is None
    assert port.type is None


def test_share_size_bytes_none_when_all_missing() -> None:
    """Test Share.size_bytes returns None when size, used, and free are all missing."""
    share = models.Share(id="share:1", name="empty", size=None, used=None, free=None)
    assert share.size_bytes is None


def test_share_size_bytes_with_valid_size() -> None:
    """Test Share.size_bytes uses size when it's non-zero."""
    share = models.Share(id="share:1", name="data", size=1000, used=500, free=500)
    assert share.size_bytes == 1000 * 1024  # Uses size directly when non-zero


def test_share_used_bytes_none() -> None:
    """Test Share.used_bytes returns None when used is None."""
    share = models.Share(id="share:1", name="empty", used=None)
    assert share.used_bytes is None


def test_share_free_bytes_none() -> None:
    """Test Share.free_bytes returns None when free is None."""
    share = models.Share(id="share:1", name="empty", free=None)
    assert share.free_bytes is None


def test_share_usage_percent_none_when_used_none() -> None:
    """Test Share.usage_percent returns None when used is None."""
    share = models.Share(id="share:1", name="data", size=1000, used=None, free=500)
    assert share.usage_percent is None


def test_disk_fs_used_bytes_none() -> None:
    """Test ArrayDisk.fs_used_bytes returns None when fsUsed is None."""
    disk = models.ArrayDisk(id="disk:1", fs_used=None)
    assert disk.fs_used_bytes is None


def test_disk_fs_free_bytes_none() -> None:
    """Test ArrayDisk.fs_free_bytes returns None when fsFree is None."""
    disk = models.ArrayDisk(id="disk:1", fs_free=None)
    assert disk.fs_free_bytes is None


def test_disk_fs_size_bytes_none() -> None:
    """Test ArrayDisk.fs_size_bytes returns None when fsSize is None."""
    disk = models.ArrayDisk(id="disk:1", fs_size=None)
    assert disk.fs_size_bytes is None


def test_disk_usage_percent_none_when_fsused_none() -> None:
    """Test ArrayDisk.usage_percent returns None when fsUsed is None."""
    disk = models.ArrayDisk(id="disk:1", fs_size=1000, fs_used=None)
    assert disk.usage_percent is None


def test_array_parities_and_caches() -> None:
    """Test array parities and caches lists parse correctly."""
    data = {
        "state": "STARTED",
        "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
        "parities": [{"id": "parity:1", "name": "Parity", "type": "PARITY"}],
        "caches": [{"id": "cache:1", "name": "Cache", "type": "CACHE"}],
    }
    array = models.UnraidArray.model_validate(data)
    assert len(array.parities) == 1
    assert array.parities[0].id == "parity:1"
    assert len(array.caches) == 1
    assert array.caches[0].id == "cache:1"
