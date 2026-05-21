"""Define mocks and test objects."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

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
async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zeversolar_data: ZeverSolarData,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the Zeversolar integration for testing."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zeversolar.coordinator.zeversolar.ZeverSolarClient.get_data",
        return_value=zeversolar_data,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry
