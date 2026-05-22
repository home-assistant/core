"""Define mocks and test objects."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest
from zeversolar import StatusEnum, ZeverSolarData

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import MOCK_HOST_ZEVERSOLAR, MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST_ZEVERSOLAR},
        unique_id=MOCK_SERIAL_NUMBER,
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
        serial_number=MOCK_SERIAL_NUMBER,
        pac=1234,
        energy_today=123,
        status=StatusEnum.OK,
        meter_status=StatusEnum.OK,
    )


@pytest.fixture
def mock_zeversolar_client(zeversolar_data: ZeverSolarData) -> Generator[MagicMock]:
    """Mock the ZeverSolar client."""
    with (
        patch(
            "homeassistant.components.zeversolar.coordinator.zeversolar.ZeverSolarClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.zeversolar.config_flow.zeversolar.ZeverSolarClient",
            new=mock_client,
        ),
    ):
        mock_client.return_value.get_data.return_value = zeversolar_data
        yield mock_client.return_value


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zeversolar_client: MagicMock,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the Zeversolar integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
