"""bosch_shc session fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

# Every collection the binary_sensor platform reads off
# ``session.device_helper`` during setup. Tests inject devices into the
# relevant list before calling ``setup_integration``; everything else stays
# empty.
DEVICE_HELPER_COLLECTIONS = (
    "motion_detectors",
    "shutter_contacts",
    "shutter_contacts2",
    "smoke_detectors",
    "thermostats",
    "twinguards",
    "universal_switches",
    "wallthermostats",
    "water_leakage_detectors",
)


def make_device(
    device_id: str = "device-1",
    name: str = "Test device",
    **attrs: object,
) -> MagicMock:
    """Build a mock SHC device with the attributes the entity base needs."""
    device = MagicMock()
    device.id = device_id
    device.name = name
    device.serial = device_id
    device.root_device_id = "shc-root"
    device.device_model = "TEST_MODEL"
    device.manufacturer = "BOSCH"
    device.status = "AVAILABLE"
    device.device_services = []
    for key, value in attrs.items():
        setattr(device, key, value)
    return device


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked Bosch SHC config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "/etc/bosch_shc/test-cert.pem",
            CONF_SSL_KEY: "/etc/bosch_shc/test-key.pem",
        },
    )


@pytest.fixture
def mock_device_helper() -> MagicMock:
    """Return a device_helper whose collections are all empty by default."""
    helper = MagicMock()
    for collection in DEVICE_HELPER_COLLECTIONS:
        setattr(helper, collection, [])
    return helper


@pytest.fixture
def mock_session(mock_device_helper: MagicMock) -> MagicMock:
    """Return a mocked SHCSession."""
    session = MagicMock()
    session.device_helper = mock_device_helper
    session.information = MagicMock()
    session.information.unique_id = "test-mac"
    session.information.updateState = None
    session.information.version = "10.0.0"
    session.start_polling = MagicMock()
    session.stop_polling = MagicMock()
    return session


@pytest.fixture
def mock_setup_dependencies(mock_session: MagicMock) -> Generator[MagicMock]:
    """Patch the SHC session constructor used during config entry setup."""
    with patch(
        "homeassistant.components.bosch_shc.SHCSession",
        return_value=mock_session,
    ):
        yield mock_session
