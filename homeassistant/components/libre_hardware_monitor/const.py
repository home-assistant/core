"""Constants for the LibreHardwareMonitor integration."""

from homeassistant.const import UnitOfInformation

DOMAIN = "libre_hardware_monitor"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8085
DEFAULT_SCAN_INTERVAL = 10

LEGACY_THROUGHPUT_UNIT = "KB/s"
THROUGHPUT_UNIQUE_ID_FRAGMENT = "throughput"

# LHM labels its data sizes MB and GB but calculates them with binary multiples
LEGACY_DATA_SIZE_UNIT_EQUIVALENTS: dict[str | None, str] = {
    "MB": UnitOfInformation.MEBIBYTES,
    "GB": UnitOfInformation.GIBIBYTES,
}
