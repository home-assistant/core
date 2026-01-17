"""Tests for the Unraid integration."""

from unraid_api.models import ServerInfo


def create_mock_server_info(
    uuid: str | None = "test-uuid-123",
    hostname: str = "tower",
    unraid_version: str = "7.2.0",
    api_version: str = "4.29.2",
) -> ServerInfo:
    """Create a mock ServerInfo object."""
    return ServerInfo(
        uuid=uuid,
        hostname=hostname,
        manufacturer="Lime Technology",
        model=f"Unraid {unraid_version}",
        sw_version=unraid_version,
        hw_version="6.1.0",
        serial_number=None,
        hw_manufacturer="ASUS",
        hw_model="Pro WS",
        os_distro="Unraid",
        os_release=unraid_version,
        os_arch="x86_64",
        api_version=api_version,
        lan_ip="192.168.1.100",
        local_url="http://192.168.1.100",
        remote_url=None,
        license_type="Pro",
        license_state="valid",
        cpu_brand="Intel Core i7",
        cpu_cores=8,
        cpu_threads=16,
    )
