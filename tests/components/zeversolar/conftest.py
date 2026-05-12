"""Define fixtures for Zeversolar tests."""

import pytest
from zeversolar import StatusEnum, ZeverSolarData

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"
MOCK_SERIAL_NUMBER = "123456778"


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        unique_id=MOCK_SERIAL_NUMBER,
    )


@pytest.fixture
def zeversolar_data() -> ZeverSolarData:
    """Create a ZeverSolarData structure for tests."""
    return ZeverSolarData(
        wifi_enabled=False,
        serial_or_registry_id="EAB9615C0001",
        registry_key="WSMQKHTQ3JVYQWA9",
        hardware_version="M10",
        software_version="19703-826R+17511-707R",
        reported_datetime="19900101 23:01:45",
        communication_status=StatusEnum.OK,
        num_inverters=1,
        serial_number=MOCK_SERIAL_NUMBER,
        pac=1234,
        energy_today=123.4,
        status=StatusEnum.OK,
        meter_status=StatusEnum.OK,
    )
