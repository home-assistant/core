"""Define mocks and test objects."""

import pytest
from zeversolar import StatusEnum, ZeverSolarData

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

MOCK_HOST_ZEVERSOLAR = "zeversolar-fake-host"
MOCK_PORT_ZEVERSOLAR = 10200


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock config entry."""

    return MockConfigEntry(
        data={
            CONF_HOST: MOCK_HOST_ZEVERSOLAR,
            CONF_PORT: MOCK_PORT_ZEVERSOLAR,
        },
        domain=DOMAIN,
        unique_id="my_id_2",
    )


@pytest.fixture
def zeversolar_data() -> ZeverSolarData:
    """Create a ZeverSolarData structure for tests."""

    return ZeverSolarData(
        wifi_enabled=False,
        serial_or_registry_id="1223",
        registry_key="A-2",
        hardware_version="M10",
        software_version="123-23",
        reported_datetime="19900101 23:00",
        communication_status=StatusEnum.OK,
        num_inverters=1,
        serial_number="123456778",
        pac=1234,
        energy_today=123,
        status=StatusEnum.OK,
        meter_status=StatusEnum.OK,
    )
