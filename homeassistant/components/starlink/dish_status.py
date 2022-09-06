"""Defines the API response when querying the addon for Starlink metrics."""
from dataclasses import dataclass


@dataclass
class DishyStatus:
    """Contains all details about the Starlink Dishy that were retrieved."""

    id: str
    hardware_version: str
    software_version: str
    boot_count: int
    uptime: int
    downlink_throughput_bps: float
    uplink_throughput_bps: float
    pop_ping_latency_ms: float
    snr_good: bool
    avg_obstruction_duration: float
    connection_valid_time: float
    direction_azimuth: float
    direction_elevation: float
