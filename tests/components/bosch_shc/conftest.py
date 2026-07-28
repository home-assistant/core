"""bosch_shc session fixtures."""

from unittest.mock import MagicMock, create_autospec

from boschshcpy import SHCDevice, SHCIntrusionSystem
import pytest


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_device() -> MagicMock:
    """Build a minimal SHCDevice double."""
    device = create_autospec(SHCDevice, instance=True, spec_set=True)
    device.id = "hdm:HomeMaticIP:contact1"
    device.serial = "serial-contact1"
    device.root_device_id = "test-mac"
    device.manufacturer = "Bosch"
    device.device_model = "SWD"
    device.name = "Contact"
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    return device


@pytest.fixture
def mock_intrusion_system() -> MagicMock:
    """Build a minimal SHCIntrusionSystem double."""
    domain = create_autospec(SHCIntrusionSystem, instance=True, spec_set=True)
    domain.id = "intrusionSystem"
    domain.manufacturer = "Bosch"
    domain.device_model = "IDS"
    domain.name = "Intrusion System"
    domain.deleted = False
    return domain
