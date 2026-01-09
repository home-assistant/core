"""Pydantic models for Unraid GraphQL responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse a datetime string or pass through datetime objects."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # Python's fromisoformat doesn't handle trailing Z, normalize first
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


class UnraidBaseModel(BaseModel):
    """Base model that ignores unknown fields for forward compatibility."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# System Info models


class InfoSystem(UnraidBaseModel):
    """System information model (manufacturer, model, version, serial, UUID)."""

    uuid: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    version: str | None = None
    serial: str | None = None


class CpuPackages(UnraidBaseModel):
    """CPU package information (temperature, power consumption)."""

    temp: list[float] = []
    total_power: float | None = Field(default=None, alias="totalPower")


class InfoCpu(UnraidBaseModel):
    """CPU information model (brand, threads, cores, temperature, power)."""

    brand: str | None = None
    threads: int | None = None
    cores: int | None = None
    packages: CpuPackages = CpuPackages()


class InfoOs(UnraidBaseModel):
    """Operating system information (hostname, uptime, kernel)."""

    hostname: str | None = None
    uptime: datetime | None = None
    kernel: str | None = None

    @field_validator("uptime", mode="before")
    @classmethod
    def parse_uptime(cls, value: str | datetime | None) -> datetime | None:
        """Parse uptime datetime from string."""
        return _parse_datetime(value)


class CoreVersions(UnraidBaseModel):
    """Core version information."""

    unraid: str | None = None
    api: str | None = None
    kernel: str | None = None


class InfoVersions(UnraidBaseModel):
    """Version information container."""

    core: CoreVersions = CoreVersions()


class SystemInfo(UnraidBaseModel):
    """System information including time, cpu, os, and versions."""

    time: datetime | None = None
    system: InfoSystem = InfoSystem()
    cpu: InfoCpu = InfoCpu()
    os: InfoOs = InfoOs()
    versions: InfoVersions = InfoVersions()

    @field_validator("time", mode="before")
    @classmethod
    def parse_time(cls, value: str | datetime | None) -> datetime | None:
        """Parse time datetime from string."""
        return _parse_datetime(value)


# Metrics models


class CpuUtilization(UnraidBaseModel):
    """CPU utilization metrics."""

    percent_total: float | None = Field(default=None, alias="percentTotal")


class MemoryUtilization(UnraidBaseModel):
    """Memory utilization metrics."""

    total: int | None = None
    used: int | None = None
    free: int | None = None
    available: int | None = None
    percent_total: float | None = Field(default=None, alias="percentTotal")
    swap_total: int | None = Field(default=None, alias="swapTotal")
    swap_used: int | None = Field(default=None, alias="swapUsed")
    percent_swap_total: float | None = Field(default=None, alias="percentSwapTotal")


class Metrics(UnraidBaseModel):
    """System metrics container."""

    cpu: CpuUtilization = CpuUtilization()
    memory: MemoryUtilization = MemoryUtilization()


# Array models


class CapacityKilobytes(UnraidBaseModel):
    """Storage capacity in kilobytes."""

    total: int
    used: int
    free: int


class ArrayCapacity(UnraidBaseModel):
    """Array capacity information."""

    kilobytes: CapacityKilobytes

    @property
    def total_bytes(self) -> int:
        """Return total capacity in bytes."""
        return self.kilobytes.total * 1024

    @property
    def used_bytes(self) -> int:
        """Return used space in bytes."""
        return self.kilobytes.used * 1024

    @property
    def free_bytes(self) -> int:
        """Return free space in bytes."""
        return self.kilobytes.free * 1024

    @property
    def usage_percent(self) -> float:
        """Return usage as a percentage."""
        return (
            (self.kilobytes.used / self.kilobytes.total * 100)
            if self.kilobytes.total
            else 0.0
        )


class ParityCheck(UnraidBaseModel):
    """Parity check status."""

    status: str | None = None
    progress: int | None = None
    errors: int | None = None


class ArrayDisk(UnraidBaseModel):
    """Array disk information."""

    id: str
    idx: int | None = None  # Optional - boot device doesn't have idx
    device: str | None = None
    name: str | None = None
    type: str | None = None
    size: int | None = None
    fs_size: int | None = Field(default=None, alias="fsSize")
    fs_used: int | None = Field(default=None, alias="fsUsed")
    fs_free: int | None = Field(default=None, alias="fsFree")
    fs_type: str | None = Field(default=None, alias="fsType")
    temp: int | None = None
    status: str | None = None
    is_spinning: bool | None = Field(default=None, alias="isSpinning")
    smart_status: str | None = Field(default=None, alias="smartStatus")

    @property
    def size_bytes(self) -> int | None:
        """Return size in bytes."""
        return self.size * 1024 if self.size is not None else None

    @property
    def fs_size_bytes(self) -> int | None:
        """Return filesystem size in bytes."""
        return self.fs_size * 1024 if self.fs_size is not None else None

    @property
    def fs_used_bytes(self) -> int | None:
        """Return filesystem used space in bytes."""
        return self.fs_used * 1024 if self.fs_used is not None else None

    @property
    def fs_free_bytes(self) -> int | None:
        """Return filesystem free space in bytes."""
        return self.fs_free * 1024 if self.fs_free is not None else None

    @property
    def usage_percent(self) -> float | None:
        """Return filesystem usage percentage."""
        if self.fs_size is None or self.fs_size == 0 or self.fs_used is None:
            return None
        return (self.fs_used / self.fs_size) * 100


class UnraidArray(UnraidBaseModel):
    """Unraid array information."""

    state: str | None = None
    capacity: ArrayCapacity
    parity_check_status: ParityCheck = Field(
        default=ParityCheck(), alias="parityCheckStatus"
    )
    disks: list[ArrayDisk] = []
    parities: list[ArrayDisk] = []
    caches: list[ArrayDisk] = []


# Docker models


class ContainerPort(UnraidBaseModel):
    """Docker container port mapping."""

    private_port: int | None = Field(default=None, alias="privatePort")
    public_port: int | None = Field(default=None, alias="publicPort")
    type: str | None = None


class DockerContainer(UnraidBaseModel):
    """Docker container information."""

    id: str
    name: str
    state: str | None = None
    image: str | None = None
    web_ui_url: str | None = Field(default=None, alias="webUiUrl")
    icon_url: str | None = Field(default=None, alias="iconUrl")
    ports: list[ContainerPort] = []


# VM models


class VmDomain(UnraidBaseModel):
    """Virtual machine information."""

    id: str
    name: str
    state: str | None = None
    memory: int | None = None
    vcpu: int | None = None


# UPS models


class UPSBattery(UnraidBaseModel):
    """UPS battery information."""

    charge_level: int | None = Field(default=None, alias="chargeLevel")
    estimated_runtime: int | None = Field(default=None, alias="estimatedRuntime")


class UPSPower(UnraidBaseModel):
    """UPS power information."""

    input_voltage: float | None = Field(default=None, alias="inputVoltage")
    output_voltage: float | None = Field(default=None, alias="outputVoltage")
    load_percentage: float | None = Field(default=None, alias="loadPercentage")


class UPSDevice(UnraidBaseModel):
    """UPS device information."""

    id: str
    name: str
    status: str | None = None
    battery: UPSBattery = UPSBattery()
    power: UPSPower = UPSPower()


# Share models


class Share(UnraidBaseModel):
    """User share information."""

    id: str
    name: str
    size: int | None = None  # Size in KB (often returns 0, use used+free instead)
    used: int | None = None  # Used in KB
    free: int | None = None  # Free in KB

    @property
    def size_bytes(self) -> int | None:
        """Return share size in bytes (calculates from used+free if size=0)."""
        # If size is provided and non-zero, use it
        if self.size is not None and self.size > 0:
            return self.size * 1024
        # Otherwise calculate from used + free
        if self.used is not None and self.free is not None:
            return (self.used + self.free) * 1024
        return None

    @property
    def used_bytes(self) -> int | None:
        """Return used space in bytes."""
        return self.used * 1024 if self.used is not None else None

    @property
    def free_bytes(self) -> int | None:
        """Return free space in bytes."""
        return self.free * 1024 if self.free is not None else None

    @property
    def usage_percent(self) -> float | None:
        """Return share usage percentage."""
        size = self.size_bytes
        used = self.used_bytes
        if size is None or size == 0 or used is None:
            return None
        return (used / size) * 100
